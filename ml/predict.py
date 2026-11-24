import json
from pathlib import Path

import joblib
import pandas as pd

from ml.preprocessing import FEATURES
from ml.train_model import MODELS, train_models


def load_model():
    model_path = MODELS / "best_model.pkl"
    metrics_path = MODELS / "model_metrics.json"
    if not model_path.exists() or not metrics_path.exists():
        train_models()
    model = joblib.load(model_path)
    with metrics_path.open(encoding="utf-8") as file:
        metrics = json.load(file)
    return model, metrics


def predict_price(values):
    missing = [name for name in FEATURES if name not in values]
    if missing:
        raise ValueError(f"Missing prediction fields: {', '.join(missing)}")
    model, metrics = load_model()
    prediction = max(0.0, float(model.predict(pd.DataFrame([{key: values[key] for key in FEATURES}]))[0]))
    area = float(values["area_sqft"])
    if area <= 0:
        raise ValueError("Property area must be greater than zero.")
    return {
        "predicted_price": prediction,
        "price_per_sqft": prediction / area,
        "model_name": metrics["best_model"],
    }
