"""
train_regressor.py — Trains an XGBoost Regressor to predict delay minutes.
"""
import joblib
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from pathlib import Path

from src.features.build_training_features import FEATURE_COLUMNS, REGRESSION_TARGET

FEATURES_PATH = "data/processed/train_features.csv"
MODEL_PATH    = "models/delay_regressor.pkl"

def train(features_path: str = FEATURES_PATH, model_path: str = MODEL_PATH):
    print("Loading features...")
    df = pd.read_csv(features_path)
    
    # Optional sanity check: filter out extreme anomalies or entirely null targets
    df = df.dropna(subset=[REGRESSION_TARGET])
    
    X = df[FEATURE_COLUMNS].values
    y = df[REGRESSION_TARGET].values
    print(f"  {len(df):,} rows loaded")
    print(f"  Average delay target: {y.mean():.1f} minutes")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    print("Training XGBRegressor...")
    xgb_model = XGBRegressor(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    
    xgb_model.fit(X_train, y_train)

    print("Evaluating Regression Model...")
    y_pred = xgb_model.predict(X_test)
    y_pred = [max(0, p) for p in y_pred] # Clip negative predictions
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred, squared=False)
    r2 = r2_score(y_test, y_pred)

    print(f"  Mean Absolute Error (MAE):  {mae:.2f} min")
    print(f"  Root Mean Sq Error (RMSE):  {rmse:.2f} min")
    print(f"  R-squared (R2):             {r2:.4f}")

    # Save the model
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model_name": "xgboost_regressor",
        "model": xgb_model,
        "features": FEATURE_COLUMNS,
    }
    joblib.dump(bundle, model_path)
    
    print(f"Saved regressor bundle to {model_path}")

if __name__ == "__main__":
    train()
