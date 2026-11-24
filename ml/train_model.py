import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.fallback_models import NumpyBoostingRegressor, NumpyForestRegressor, NumpyTreeRegressor
from ml.preprocessing import FEATURES, TARGET, build_preprocessor

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.tree import DecisionTreeRegressor

    TREE_IMPORT_ERROR = None
except ImportError as error:
    GradientBoostingRegressor = NumpyBoostingRegressor
    RandomForestRegressor = NumpyForestRegressor
    DecisionTreeRegressor = NumpyTreeRegressor
    TREE_IMPORT_ERROR = str(error)


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset" / "house_prices.csv"
MODELS = ROOT / "trained_models"
PERFORMANCE = ROOT / "static" / "images" / "model_comparison.png"


def create_demo_dataset(path=DATASET, rows=1800, seed=41):
    """Create reproducible synthetic examples, not real transaction records."""
    rng = np.random.default_rng(seed)
    cities = {
        "Bengaluru": (7200, ["Whitefield", "Sarjapur Road", "Electronic City", "Indiranagar"]),
        "Mumbai": (14500, ["Powai", "Thane", "Andheri", "Navi Mumbai"]),
        "Pune": (6900, ["Baner", "Hinjewadi", "Wakad", "Kharadi"]),
        "Hyderabad": (6500, ["Gachibowli", "Kondapur", "Miyapur", "Banjara Hills"]),
        "Delhi": (8200, ["Dwarka", "Rohini", "Saket", "Noida Extension"]),
        "Chennai": (6100, ["OMR", "Velachery", "Porur", "Anna Nagar"]),
        "Kolkata": (4900, ["New Town", "Salt Lake", "Rajarhat", "Behala"]),
        "Ahmedabad": (5300, ["Satellite", "Bopal", "Prahlad Nagar", "Gota"]),
    }
    kinds = ["Apartment", "Villa", "Independent House"]
    city_values = rng.choice(list(cities), rows)
    records = []
    for city in city_values:
        base, localities = cities[city]
        location = rng.choice(localities)
        kind = rng.choice(kinds, p=[0.66, 0.17, 0.17])
        area = int(np.clip(rng.normal(1350, 520), 450, 4800))
        bedrooms = int(np.clip(round(area / 520 + rng.normal(0.7, 0.75)), 1, 6))
        bathrooms = int(np.clip(bedrooms - rng.choice([0, 0, 1]), 1, 5))
        age = int(rng.integers(0, 36))
        parking = rng.choice(["Yes", "No"], p=[0.78, 0.22])
        furnishing = rng.choice(["Unfurnished", "Semi-furnished", "Furnished"], p=[0.39, 0.43, 0.18])
        locality_premium = (localities.index(location) % 4) * 0.075
        kind_premium = {"Apartment": 1.0, "Villa": 1.22, "Independent House": 1.11}[kind]
        furnishing_premium = {"Unfurnished": 0, "Semi-furnished": 0.035, "Furnished": 0.07}[furnishing]
        rate = base * kind_premium * (1 + locality_premium + furnishing_premium)
        rate *= 1 + (0.055 if parking == "Yes" else 0) - min(age, 30) * 0.003
        price = area * rate * (1 + rng.normal(0, 0.12))
        records.append({
            "city": city, "location": location, "property_type": kind,
            "area_sqft": area, "bedrooms": bedrooms, "bathrooms": bathrooms,
            "property_age": age, "parking": parking, "furnishing": furnishing,
            "price": max(900000, round(price / 10000) * 10000),
        })
    frame = pd.DataFrame(records, columns=FEATURES + [TARGET])
    # Include a few incomplete rows to exercise the fitted imputation pipeline.
    for column in ("bathrooms", "furnishing"):
        frame.loc[rng.choice(frame.index, size=max(1, rows // 100), replace=False), column] = np.nan
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def prepare_data(path=DATASET):
    if not Path(path).exists():
        frame = create_demo_dataset(Path(path))
    else:
        frame = pd.read_csv(path)
    missing = [column for column in FEATURES + [TARGET] if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    frame = frame[FEATURES + [TARGET]].drop_duplicates().copy()
    frame[TARGET] = pd.to_numeric(frame[TARGET], errors="coerce")
    frame = frame.dropna(subset=[TARGET])
    frame = frame[frame[TARGET].between(300_000, 1_000_000_000)]
    for column in ["area_sqft", "bedrooms", "bathrooms", "property_age"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[(frame["area_sqft"].isna()) | frame["area_sqft"].between(200, 20000)]
    frame = frame.reset_index(drop=True)
    if len(frame) < 30:
        raise ValueError("At least 30 valid housing rows are required to train models.")
    return frame


def train_models():
    frame = prepare_data()
    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURES], frame[TARGET], test_size=0.2, random_state=42
    )
    estimators = {
        "Linear Regression": LinearRegression(),
        "Decision Tree Regression": DecisionTreeRegressor(max_depth=8, min_samples_leaf=6, random_state=42),
        "Random Forest Regression": RandomForestRegressor(
            n_estimators=28, min_samples_leaf=8, max_features="sqrt", random_state=42,
        ) if TREE_IMPORT_ERROR else RandomForestRegressor(
            n_estimators=140, min_samples_leaf=2, max_features=0.9,
            random_state=42, n_jobs=-1,
        ),
        "Gradient Boosting Regression": GradientBoostingRegressor(
            n_estimators=36, learning_rate=0.07, random_state=42,
        ) if TREE_IMPORT_ERROR else GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.06, max_depth=2,
            loss="huber", random_state=42,
        ),
    }
    metrics = {}
    fitted = {}
    for name, estimator in estimators.items():
        pipeline = Pipeline([
            ("preprocessor", build_preprocessor()),
            ("regressor", estimator),
        ])
        pipeline.fit(x_train, y_train)
        predicted = pipeline.predict(x_test)
        mse = mean_squared_error(y_test, predicted)
        metrics[name] = {
            "mae": float(mean_absolute_error(y_test, predicted)),
            "mse": float(mse),
            "rmse": float(np.sqrt(mse)),
            "r2": float(r2_score(y_test, predicted)),
        }
        fitted[name] = pipeline
    best_name = min(metrics, key=lambda model: metrics[model]["rmse"])
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[best_name], MODELS / "best_model.pkl")
    joblib.dump(fitted[best_name].named_steps["preprocessor"], MODELS / "preprocessing_pipeline.pkl")
    with (MODELS / "model_metrics.json").open("w", encoding="utf-8") as file:
        json.dump({"best_model": best_name, "metrics": metrics, "dataset_rows": len(frame),
                   "dataset_note": "Synthetic demonstration data; not actual market transactions.",
                   "tree_backend": "NumPy fallback (native scikit-learn tree extension blocked by Windows policy)"
                   if TREE_IMPORT_ERROR else "scikit-learn native tree estimators"},
                  file, indent=2)
    names = list(metrics)
    fig, axis = plt.subplots(figsize=(9, 4.8))
    axis.bar(names, [metrics[name]["rmse"] / 1_000_000 for name in names], color="#16856b")
    axis.set_ylabel("RMSE (INR millions)")
    axis.set_title("Held-out test RMSE by regression model")
    axis.tick_params(axis="x", rotation=18)
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    PERFORMANCE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PERFORMANCE, dpi=160)
    plt.close(fig)
    return best_name, metrics


if __name__ == "__main__":
    selected, results = train_models()
    print(f"Best model by lowest held-out RMSE: {selected}")
    for model, values in results.items():
        print(f"{model}: MAE INR {values['mae']:,.0f} | RMSE INR {values['rmse']:,.0f} | R2 {values['r2']:.3f}")
