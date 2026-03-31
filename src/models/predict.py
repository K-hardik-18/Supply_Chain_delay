"""
predict.py  —  Load the model bundle and make predictions.

Handles both tree-based models (RF, XGBoost) and linear models (LR)
that require feature scaling.
"""

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from functools import lru_cache

MODEL_PATH = "models/delay_classifier.pkl"
REGRESSOR_PATH = "models/delay_regressor.pkl"


@lru_cache(maxsize=1)
def _load_bundle(path: str = MODEL_PATH) -> dict:
    """Load the ML model bundle once and cache it in memory."""
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Model not found at '{path}'. "
            "Run: python -m src.models.train_classifier (or train_regressor)"
        )
    return joblib.load(path)


def get_model(path: str = MODEL_PATH):
    return _load_bundle(path)["model"]


def get_model_name(path: str = MODEL_PATH) -> str:
    return _load_bundle(path).get("model_name", "xgboost")


def get_threshold(path: str = MODEL_PATH) -> float:
    return float(_load_bundle(path).get("threshold", 0.42))


def get_feature_columns(path: str = MODEL_PATH) -> list:
    return _load_bundle(path)["feature_columns"]


def predict_delay(
    features: pd.DataFrame,
    model_path: str = MODEL_PATH,
    regressor_path: str = REGRESSOR_PATH,
) -> tuple[float, bool, float]:
    """
    Returns (delay_probability, is_delayed, predicted_delay_minutes).

    Parameters
    ----------
    features : single-row DataFrame produced by build_inference_features
    """
    bundle    = _load_bundle(model_path)
    model     = bundle["model"]
    threshold = bundle.get("threshold", 0.42)
    needs_scaling = bundle.get("needs_scaling", False)
    scaler    = bundle.get("scaler", None)

    input_data = features
    if needs_scaling and scaler is not None:
        input_data = pd.DataFrame(
            scaler.transform(features),
            columns=features.columns,
        )

    # 1. Classification
    prob     = float(model.predict_proba(input_data)[0][1])
    delayed  = prob >= threshold

    # 2. Regression
    pred_mins = 0.0
    try:
        reg_bundle = _load_bundle(regressor_path)
        reg_model = reg_bundle["model"]
        pred_mins = float(reg_model.predict(input_data)[0])
        pred_mins = max(0.0, pred_mins)
    except FileNotFoundError:
        pass # Graceful fallback if regressor is missing

    return prob, delayed, pred_mins
