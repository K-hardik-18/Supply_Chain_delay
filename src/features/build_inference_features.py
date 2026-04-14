"""
build_inference_features.py  —  Build one feature vector from an API request.

CRITICAL CONTRACT:
  Every feature computed here must match FEATURE_COLUMNS from
  build_training_features.py exactly — same column name, same scale,
  same encoding. This is the file that prevents training/serving skew.

There is NO randomness here. Same inputs always produce the same features.
"""

import math
import pandas as pd
from datetime import datetime

from .build_training_features import FEATURE_COLUMNS
from src.simulator.hubs import get_hub, HUB_TYPE_CODE
from src.simulator.network import haversine
from src.simulator.traffic import (
    estimate_traffic, encode_traffic, expected_traffic_code,
    waiting_time_for, demand_pressure,
    hub_congestion_for,
    PEAK_HOURS,
)
from src.simulator.weather import (
    default_weather, encode_weather,
    try_live_weather,
)
from src.simulator.shipments import encode_vehicle, encode_cargo
from src.utils.traffic_api import get_traffic_delay, convert_traffic
from src.utils.osrm_api import get_osrm_route


# In-memory cache for feature vectors (same inputs → same features)
_feature_cache: dict[str, pd.DataFrame] = {}

def build_feature_vector(
    source: str,
    destination: str,
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str   = "standard",
    priority_level: int = 2,
    weather_api_key: str | None = None,
    traffic_api_key: str | None = None,
    use_osrm: bool = True,
) -> pd.DataFrame:
    """
    Build a single-row feature DataFrame for the ML model.

    Parameters
    ----------
    source, destination : hub city names (must exist in hubs.py)
    departure_time      : ISO 8601 string, e.g. "2024-07-15T09:30:00"
    vehicle_type        : "bike" | "van" | "truck"
    cargo_type          : "standard" | "perishable" | "fragile"
    priority_level      : 1 | 2 | 3
    weather_api_key     : optional Visual Crossing key; fallback to seasonal default
    """

    # ── Cache check ──────────────────────────────────────────────────────────
    _cache_key = f"{source}|{destination}|{departure_time}|{vehicle_type}|{cargo_type}|{priority_level}"
    if _cache_key in _feature_cache:
        return _feature_cache[_cache_key].copy()

    # ── Hub lookup ───────────────────────────────────────────────────────────
    src_hub = get_hub(source)
    dst_hub = get_hub(destination)

    # ── Route features — OSRM with haversine fallback ─────────────────
    estimated_time_hr = None
    if use_osrm:
        dist_km, dur_hr, _geom = get_osrm_route(
            src_hub["lat"], src_hub["lon"],
            dst_hub["lat"], dst_hub["lon"]
        )
        if dist_km is not None:
            distance_km = dist_km
            estimated_time_hr = dur_hr

    if estimated_time_hr is None:
        # Haversine fallback
        distance_km = haversine(src_hub["lat"], src_hub["lon"],
                                dst_hub["lat"], dst_hub["lon"])
        # Estimate time using base speed
        speed = 35 if distance_km < 80 else (55 if distance_km < 250 else 75)
        estimated_time_hr = round(distance_km / speed, 2)

    route_type_code = 0 if distance_km < 80 else (1 if distance_km < 250 else 2)
    source_hub_type_code = HUB_TYPE_CODE[src_hub["type"]]
    dest_hub_type_code   = HUB_TYPE_CODE[dst_hub["type"]]

    # ── Time features ────────────────────────────────────────────────────────
    dt         = datetime.fromisoformat(departure_time)
    hour       = dt.hour
    dayofweek  = dt.weekday()
    month      = dt.month
    is_weekend = int(dayofweek >= 5)
    is_peak    = int(hour in PEAK_HOURS and not is_weekend)
    hour_sin   = math.sin(2 * math.pi * hour / 24)
    hour_cos   = math.cos(2 * math.pi * hour / 24)
    dp         = demand_pressure(hour)

    # ── Traffic features — use expected value to match training distribution ──
    # estimate_traffic() argmax (e.g. always "clear" at 2pm) causes training/
    # serving skew because training sampled randomly. expected_traffic_code()
    # returns a probability-weighted continuous value that represents what the
    # model actually learned during training.
    # 🔹 Simulated (original)
    simulated_traffic = expected_traffic_code(hour, bool(is_weekend))

    if traffic_api_key:
        delay_ratio = get_traffic_delay(
            src_hub["lat"], src_hub["lon"],
            dst_hub["lat"], dst_hub["lon"],
            traffic_api_key
        )
        real_traffic = convert_traffic(delay_ratio)
    else:
        real_traffic = simulated_traffic

    # 🔹 Hybrid (IMPORTANT)
    traffic_code = 0.7 * simulated_traffic + 0.3 * real_traffic

    # For waiting time (keep label logic)
    traffic_label = estimate_traffic(hour, bool(is_weekend))
    wait = waiting_time_for(traffic_label)

    # ── Weather features — live API, else seasonal default ───────────────────
    weather_live, temp_live = try_live_weather(src_hub["city"], weather_api_key, departure_time)

    if weather_live is not None:
        weather      = weather_live
        temperature  = temp_live
    else:
        weather, temperature = default_weather(month)

    weather_code = encode_weather(weather)

    # ── Hub congestion — deterministic from hour + hub capacity ─────────────
    hub_congestion = hub_congestion_for(dp, src_hub["capacity"])

    # ── Shipment encoding ────────────────────────────────────────────────────
    vehicle_code   = encode_vehicle(vehicle_type)
    cargo_code     = encode_cargo(cargo_type)

    # ── Interaction features — same formulas as generator.py ─────────────────
    traffic_x_peak       = traffic_code * is_peak
    weather_x_distance   = weather_code * (distance_km / 500.0)
    congestion_x_waiting = hub_congestion * (wait / 60.0)
    temp_x_cargo         = (temperature / 50.0) * (cargo_code == 1)

    # ── Time & Duration Features (Regression Ready) ──────────────────────────
    base_duration = estimated_time_hr
    traffic_multiplier = 1.0 + (traffic_code * 0.15)
    traffic_time = base_duration * traffic_multiplier + (wait / 60.0)
    traffic_delay = traffic_time - base_duration

    # ── Assemble feature dict in FEATURE_COLUMNS order ───────────────────────
    feat = {
        "distance_km":           round(distance_km, 1),
        "base_duration":         round(base_duration, 2),
        "traffic_time":          round(traffic_time, 2),
        "traffic_delay":         round(traffic_delay, 2),
        "route_type_code":       route_type_code,
        "source_hub_type_code":  source_hub_type_code,
        "dest_hub_type_code":    dest_hub_type_code,
        "departure_hour":        hour,
        "hour_sin":              round(hour_sin, 4),
        "hour_cos":              round(hour_cos, 4),
        "is_peak_hour":          is_peak,
        "is_weekend":            is_weekend,
        "demand_pressure":       round(dp, 4),
        "traffic_code":          traffic_code,
        "waiting_time_est":      round(wait, 1),
        "weather_code":          weather_code,
        "temperature":           round(temperature, 1),
        "hub_congestion":        round(hub_congestion, 4),
        "vehicle_code":          vehicle_code,
        "cargo_code":            cargo_code,
        "priority_level":        priority_level,
        "traffic_x_peak":        traffic_x_peak,
        "weather_x_distance":    round(weather_x_distance, 4),
        "congestion_x_waiting":  round(congestion_x_waiting, 4),
        "temp_x_cargo":          round(temp_x_cargo, 4),
    }

    # Return as single-row DataFrame in exact training column order
    df = pd.DataFrame([feat])[FEATURE_COLUMNS]
    _feature_cache[_cache_key] = df
    return df


def get_feature_metadata(
    source: str,
    destination: str,
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str   = "standard",
    priority_level: int = 2,
    weather_api_key: str | None = None,
) -> dict:
    """
    Same as build_feature_vector but also returns human-readable context
    (traffic label, weather label, distance, etc.) for API response display.
    """
    src_hub = get_hub(source)
    dst_hub = get_hub(destination)

    distance_km = haversine(src_hub["lat"], src_hub["lon"],
                            dst_hub["lat"], dst_hub["lon"])

    dt        = datetime.fromisoformat(departure_time)
    hour      = dt.hour
    month     = dt.month
    is_weekend = int(dt.weekday() >= 5)
    is_peak   = int(hour in PEAK_HOURS and not is_weekend)

    traffic       = estimate_traffic(hour, bool(is_weekend))   # label only
    traffic_code  = encode_traffic(traffic)
    wait          = waiting_time_for(traffic)

    weather_live, temp_live = try_live_weather(src_hub["city"], weather_api_key)
    weather, temperature = (weather_live, temp_live) if weather_live else default_weather(month)

    return {
        "distance_km":    round(distance_km, 1),
        "traffic_level":  traffic,
        "weather":        weather,
        "temperature":    round(temperature, 1),
        "is_peak_hour":   bool(is_peak),
        "is_weekend":     bool(is_weekend),
        "waiting_min":    round(wait, 1),
    }
