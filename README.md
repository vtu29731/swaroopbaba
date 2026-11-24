# HomeValue

HomeValue is a full-stack academic demonstration of property discovery and house-price regression using Flask, SQLite, and scikit-learn. The included housing CSV is **synthetic demonstration data**, generated to exercise the application and machine-learning workflow. It does not represent actual market transactions or support a guaranteed valuation.

## Features

- Responsive landing page, property search and details, and demo sample listings.
- Responsive React login/registration screens with password visibility controls and a clearly labeled manual house-details form.
- User registration/login with Werkzeug password hashing, private dashboards and prediction history.
- Saved properties, prediction form/result, and server-side validation.
- Admin sign-in, listing CRUD, user/prediction views, and model metrics.
- Four trained regression models with held-out MAE, MSE, RMSE, and R² comparison.
- Persisted scikit-learn preprocessing/model pipelines; app predictions use the selected fitted model.
- SQLite initialization and sample listing seeding on first run.

## Requirements

Python 3.10+ and pip. Windows commands below use PowerShell. From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

## Prepare, train, and run

The training script creates `dataset/house_prices.csv` when it does not exist. You may instead provide a CSV with `city, location, property_type, area_sqft, bedrooms, bathrooms, property_age, parking, furnishing, price` columns. Categorical columns are one-hot encoded; numeric fields are median-imputed and scaled. Invalid target rows, out-of-range values and duplicate records are removed.

```powershell
python -m ml.train_model
python -c "from app import app; app.app_context().push(); print('SQLite database initialized')"
python app.py
```

The second command is optional because the database is initialized automatically when the app starts. Open <http://127.0.0.1:5000>.

The React application is served by the same Flask app at <http://127.0.0.1:5000/react>. Its source is in `static/react/App.js` and `static/react/react.css`; it uses the local JSON API, while React and ReactDOM are loaded from public CDNs in the browser. The rest of the server-rendered pages remain available from the home page. Browser access requires an internet connection to fetch those React libraries.

On a first run, if the model files are missing, the application trains them automatically. Training outputs are saved under `trained_models/`; the comparison chart is written to `static/images/model_comparison.png`.

## Deploy a public website on Render

The GitHub repository stores the source; Render runs the Flask and machine-learning backend and provides the public HTTPS address. The included `render.yaml` configures Render's free web service. Its local SQLite database is ephemeral: user accounts, saved homes, and prediction history may be lost when the service restarts or redeploys. Render free services may also sleep when idle. Persistent data requires upgrading the service and attaching persistent storage, which may incur charges.

1. Create an empty repository on GitHub. From the project folder, install Git for Windows if needed, then publish the source:

   ```powershell
   git init
   git add .
   git commit -m "Initial HomeValue implementation"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
   git push -u origin main
   ```

   Replace the remote URL with your repository address. Include `dataset/house_prices.csv`; the SQLite database and generated model files are ignored by Git.

2. Sign in at [Render](https://render.com), choose **New → Blueprint**, and connect your GitHub repository.
3. Render reads `render.yaml`, installs dependencies, trains the models from the demonstration dataset, and starts the Gunicorn server.
4. In Render's prompted environment settings, provide a unique admin username and a strong admin password. Keep the generated `HOMEVALUE_SECRET_KEY` private.
5. After the deployment health check passes, open the Render-provided `https://…onrender.com/react` address. The Flask pages remain available at the root URL.

On the free plan, the SQLite database is in the app's local `instance` directory and is not persistent. Upgrade the service and configure a persistent disk plus `HOMEVALUE_DATABASE` before relying on account or prediction history. The admin account is initialized on the first database creation; changing the environment password later does not change an already-created admin password.

## Accounts

- Register an ordinary user through the website.
- Local admin defaults: username `admin@homevalue.local`, password `ChangeMe123!`, at `/admin/login`.
- Set `HOMEVALUE_ADMIN_USER` and `HOMEVALUE_ADMIN_PASSWORD` before the first database initialization to choose admin credentials. Change the local default before using beyond a private development machine.

The session secret can be overridden with `HOMEVALUE_SECRET_KEY`. The SQLite file defaults to `instance/homevalue.db`; override with `HOMEVALUE_DATABASE`. The database and generated model files are ignored by Git.

## Model and evaluation notes

All four regressors train and evaluate using a reproducible 80/20 split. The selected model is the one with the lowest test RMSE. MAE, MSE, RMSE, R², selected model, and the synthetic-data note are recorded in `trained_models/model_metrics.json`; the performance page reads those actual training results. The pipeline is fitted only on training data and then applied to held-out rows and predictions. Synthetic prices are generated from plausible city-level rate ranges with area, property type, locality, parking, furnishing, age and random variation. They must not be interpreted as market data.

On Windows systems where application-control policy blocks scikit-learn's compiled tree extension, training automatically uses the included NumPy decision-tree, random-forest, and gradient-boosting estimators; the linear model and fitted scikit-learn preprocessing pipeline remain in use. The selected backend is recorded with the evaluation metrics.

## Project layout

```text
HomeValue/
├── app.py
├── backend/              # Flask routes, authentication and SQLite helpers
├── dataset/              # Generated/provided housing CSV
├── instance/             # SQLite database
├── ml/                   # Dataset, preprocessing, training and prediction
├── static/               # CSS, JavaScript and generated comparison chart
├── templates/            # Jinja pages
└── trained_models/       # Selected model, preprocessor and evaluation metrics
```
