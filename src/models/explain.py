"""
explain.py  —  Per-prediction SHAP explanations.

Supports TreeExplainer (XGBoost, Random Forest) and
KernelExplainer fallback (Logistic Regression).
"""

import shap
import numpy as np
import pandas as pd
from functools import lru_cache

from .predict import _load_bundle

MODEL_PATH = "models/delay_classifier.pkl"

# Human-readable feature descriptions for the dashboard
FEATURE_LABELS = {
    "distance_km":           "Route distance",
    "route_type_code":       "Road type",
    "source_hub_type_code":  "Origin hub type",
    "dest_hub_type_code":    "Destination hub type",
    "departure_hour":        "Departure hour",
    "hour_sin":              "Hour (cyclic sin)",
    "hour_cos":              "Hour (cyclic cos)",
    "is_peak_hour":          "Peak hour",
    "is_weekend":            "Weekend shipment",
    "demand_pressure":       "Network demand",
    "traffic_code":          "Traffic severity",
    "waiting_time_est":      "Estimated wait time",
    "weather_code":          "Weather severity",
    "temperature":           "Temperature",
    "hub_congestion":        "Hub congestion",
    "vehicle_code":          "Vehicle type",
    "cargo_code":            "Cargo sensitivity",
    "priority_level":        "Shipment priority",
    "traffic_x_peak":        "Traffic × peak interaction",
    "weather_x_distance":    "Weather × distance risk",
    "congestion_x_waiting":  "Congestion × wait risk",
    "temp_x_cargo":          "Temperature × cargo risk",
}


@lru_cache(maxsize=1)
def _get_explainer(model_path: str = MODEL_PATH):
    """
    Create the appropriate SHAP explainer for the saved model.
    TreeExplainer for tree-based, LinearExplainer for LR.
    """
    bundle = _load_bundle(model_path)
    model = bundle["model"]
    model_name = bundle.get("model_name", "xgboost")
    needs_scaling = bundle.get("needs_scaling", False)
    scaler = bundle.get("scaler", None)

    if model_name == "logistic_regression":
        # LinearExplainer works well for logistic regression
        return shap.LinearExplainer(model, masker=None), needs_scaling, scaler
    else:
        return shap.TreeExplainer(model), needs_scaling, scaler


def explain_prediction(
    features: pd.DataFrame,
    top_n: int = 3,
    model_path: str = MODEL_PATH,
) -> list[dict]:
    """
    Returns top_n most influential features for this prediction.

    Each entry:
    {
        "feature":     raw feature name,
        "label":       human-readable label,
        "value":       actual feature value,
        "shap_value":  SHAP value (positive = pushes toward delay),
        "direction":   "increases_risk" | "reduces_risk",
        "magnitude":   abs(shap_value)
    }
    """
    explainer, needs_scaling, scaler = _get_explainer(model_path)

    input_data = features
    if needs_scaling and scaler is not None:
        input_data = pd.DataFrame(
            scaler.transform(features),
            columns=features.columns,
        )

    shap_values = explainer.shap_values(input_data)

    if isinstance(shap_values, list):
        values = shap_values[1][0]   # class=1 (delayed)
    elif shap_values.ndim == 2:
        values = shap_values[0]
    else:
        values = shap_values

    feature_names = features.columns.tolist()
    feature_vals  = features.iloc[0].tolist()

    importance = []
    for name, val, shap_val in zip(feature_names, feature_vals, values):
        importance.append({
            "feature":    name,
            "label":      FEATURE_LABELS.get(name, name),
            "value":      round(float(val), 3),
            "shap_value": round(float(shap_val), 4),
            "direction":  "increases_risk" if shap_val > 0 else "reduces_risk",
            "magnitude":  round(abs(float(shap_val)), 4),
        })

    importance.sort(key=lambda x: x["magnitude"], reverse=True)
    return importance[:top_n]
