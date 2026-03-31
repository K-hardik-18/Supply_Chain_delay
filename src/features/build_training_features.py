"""
build_training_features.py  —  Transform raw simulator output into ML-ready features.

This file defines the CANONICAL feature contract.
build_inference_features.py must produce the same columns in the same order.

Run:
    python -m src.features.build_training_features
"""

import math
import pandas as pd
from pathlib import Path
from src.utils.traffic_api import get_traffic_delay, convert_traffic

RAW_PATH       = "data/simulated/shipments_raw.csv"
FEATURES_PATH  = "data/processed/train_features.csv"

# ── The exact feature list the model will be trained on ──────────────────────
# Any change here MUST be mirrored in build_inference_features.py
FEATURE_COLUMNS = [
    # Route
    "distance_km",
    "base_duration",
    "traffic_time",
    "traffic_delay",
    "route_type_code",
    "source_hub_type_code",
    "dest_hub_type_code",
    # Time
    "departure_hour",
    "hour_sin",
    "hour_cos",
    "is_peak_hour",
    "is_weekend",
    "demand_pressure",
    # Traffic
    "traffic_code",
    "waiting_time_est",
    # Weather
    "weather_code",
    "temperature",
    # Hub state
    "hub_congestion",
    # Shipment
    "vehicle_code",
    "cargo_code",
    "priority_level",
    # Interaction features
    "traffic_x_peak",
    "weather_x_distance",
    "congestion_x_waiting",
    "temp_x_cargo",
]

TARGET_COLUMN = "delayed"
REGRESSION_TARGET = "delay_minutes"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute any derived features not already in the raw CSV,
    then return a clean feature DataFrame + target.
    All columns must be numeric.
    """

    # These are already computed by the generator — just verify and select
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN, REGRESSION_TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in raw data: {missing}")

    out = df[FEATURE_COLUMNS + [TARGET_COLUMN, REGRESSION_TARGET]].copy()

    # Sanity checks
    assert out.isnull().sum().sum() == 0, "Null values found in feature set"
    assert out.dtypes[TARGET_COLUMN] in ["int64", "int32", "bool"], \
        f"Target must be integer, got {out.dtypes[TARGET_COLUMN]}"

    return out


def run(raw_path: str = RAW_PATH, out_path: str = FEATURES_PATH):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading raw data from {raw_path}...")
    df = pd.read_csv(raw_path)
    print(f"  {len(df):,} rows loaded")

    features = build_features(df)

    delay_rate = features[TARGET_COLUMN].mean()
    print(f"  Delay rate: {delay_rate:.1%}")
    print(f"  Feature columns ({len(FEATURE_COLUMNS)}): {FEATURE_COLUMNS}")

    features.to_csv(out_path, index=False)
    print(f"Saved → {out_path}")
    return features


if __name__ == "__main__":
    run()
