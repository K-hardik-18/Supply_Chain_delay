"""
generator.py  —  Synthetic logistics data generator.

Generates 50,000 simulated shipments with a realistic delay label
driven by HIDDEN LATENT INTERACTION RULES (not a simple formula).

The delay target is ~35% positive rate.

Run:
    python -m src.simulator.generator
"""

import os
import math
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from .hubs import HUBS, HUB_TYPE_CODE, get_hub_df
from .network import haversine
from .traffic import (
    TRAFFIC_LEVELS, TRAFFIC_CODE_MAP,
    sample_traffic, waiting_time_for, demand_pressure,
    hub_congestion_for,
)
from .weather import (
    WEATHER_LEVELS, WEATHER_CODE_MAP,
    sample_weather,
)
from .shipments import (
    VEHICLE_TYPES, VEHICLE_CODE,
    CARGO_TYPES, CARGO_CODE,
    PRIORITY_LEVELS, PRIORITY_WEIGHTS,
    sample_shipment,
)

N_SHIPMENTS = 50_000
RANDOM_SEED = 42
OUT_PATH = "data/simulated/shipments_raw.csv"

PEAK_HOURS = [7, 8, 9, 17, 18, 19]


# ---------------------------------------------------------------------------
# LATENT DELAY RULES
# Key design principle: delay is caused by INTERACTIONS, not single features.
# No single feature can perfectly predict delay on its own.
# ---------------------------------------------------------------------------

def _compute_delay_probability(
    traffic_code: int,
    weather_code: int,
    is_peak_hour: int,
    is_weekend: int,
    distance_km: float,
    hub_congestion: float,
    waiting_time_est: float,
    temperature: float,
    cargo_code: int,
    vehicle_code: int,
    priority_level: int,
    demand_pressure_val: float,
) -> float:
    """
    Compute base delay probability.

    Design goals:
      - Distance + weather cause meaningful risk even off-peak
      - Peak hour adds a fixed boost, not a multiplier (not dominant)
      - Bike + long route is genuinely dangerous regardless of hour
      - Target ~27% delay rate across the full training distribution
    """
    score = 0.04   # small base

    # ── Traffic: additive peak boost, not multiplicative ─────────────────────
    traffic_base = [0.00, 0.06, 0.14, 0.26][traffic_code]
    peak_boost   = 0.10 if is_peak_hour and not is_weekend else 0.0
    score += traffic_base + peak_boost

    # ── Distance: standalone risk, every long haul has higher exposure ────────
    score += min(0.16, distance_km / 4500)

    # ── Weather: meaningful standalone, amplified on long routes ──────────────
    weather_base = [0.00, 0.09, 0.14, 0.30][weather_code]
    dist_mult    = 1.0 + min(0.80, distance_km / 800)
    score += weather_base * dist_mult

    # ── Hub congestion: only when genuinely overloaded ────────────────────────
    if hub_congestion > 0.78:
        score += (hub_congestion - 0.78) * 0.15

    # ── Vehicle type: bike is riskier on non-trivial routes ───────────────────
    if vehicle_code == 0 and distance_km > 120:
        score += 0.06 + min(0.12, (distance_km - 120) / 2500)

    # ── Cargo sensitivity ─────────────────────────────────────────────────────
    if cargo_code == 1 and temperature > 34:      # perishable + hot weather
        score += 0.07 + (temperature - 34) * 0.015
    if cargo_code == 2 and traffic_code >= 2:     # fragile + heavy traffic
        score += 0.06

    # ── Interaction: heavy traffic + long route ───────────────────────────────
    if traffic_code >= 2 and distance_km > 300:
        score += 0.07

    # ── Interaction: storm at peak hour ───────────────────────────────────────
    if weather_code == 3 and is_peak_hour:
        score += 0.09

    # ── Demand pressure amplifier (only when already elevated) ───────────────
    if demand_pressure_val > 0.82 and score > 0.22:
        score *= 1.08

    if is_weekend:
        score -= 0.05
    if priority_level == 3:
        score += 0.03

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# SIMULATOR
# ---------------------------------------------------------------------------

def generate_dataset(n: int = N_SHIPMENTS, seed: int = RANDOM_SEED) -> pd.DataFrame:

    rng = np.random.default_rng(seed)
    hub_df = get_hub_df()
    hub_list = hub_df.to_dict("records")
    n_hubs = len(hub_list)

    # Precompute pairwise distances for hub combinations
    hub_dist = {}
    for i, h1 in enumerate(hub_list):
        for j, h2 in enumerate(hub_list):
            if i != j:
                hub_dist[(h1["city"], h2["city"])] = haversine(
                    h1["lat"], h1["lon"], h2["lat"], h2["lon"]
                )

    records = []
    n_delayed = 0

    # Simulate a year of shipments
    base_date = datetime(2024, 1, 1)

    for i in range(n):

        # ── Sample source / destination (different hubs)
        src_idx, dst_idx = rng.choice(n_hubs, size=2, replace=False)
        src = hub_list[src_idx]
        dst = hub_list[dst_idx]

        distance_km = hub_dist[(src["city"], dst["city"])]

        # ── Sample departure time (business-hours biased)
        days_offset = int(rng.integers(0, 365))
        dep_date = base_date + timedelta(days=days_offset)
        # Hour distribution: 70% between 7am-8pm, 30% rest
        if rng.random() < 0.70:
            hour = int(rng.integers(7, 20))
        else:
            hour = int(rng.integers(0, 7) if rng.random() < 0.5 else rng.integers(20, 24))
        minute = int(rng.integers(0, 60))
        dep_time = dep_date.replace(hour=hour, minute=minute)

        month      = dep_date.month
        dayofweek  = dep_date.weekday()          # 0=Mon
        is_weekend = int(dayofweek >= 5)
        is_peak    = int(hour in PEAK_HOURS and not is_weekend)

        # ── Sample traffic
        traffic = sample_traffic(hour, bool(is_weekend), rng)
        traffic_code = TRAFFIC_CODE_MAP[traffic]

        # Deterministic waiting time mean + small training noise
        wait_mean = waiting_time_for(traffic)
        waiting_time_est = float(rng.normal(wait_mean, 3.0))
        waiting_time_est = max(1.0, waiting_time_est)

        # ── Sample weather
        weather, temperature = sample_weather(month, rng)
        weather_code = WEATHER_CODE_MAP[weather]

        # ── Hub congestion: time-of-day + hub capacity effect
        time_load = demand_pressure(hour)
        hub_congestion_base = hub_congestion_for(time_load, src["capacity"])
        hub_congestion = float(rng.normal(hub_congestion_base, 0.05))
        hub_congestion = max(0.0, min(0.98, hub_congestion))   # never hard 1.0

        # ── Sample shipment profile
        shipment = sample_shipment(rng)

        # ── Demand pressure
        dp = demand_pressure(hour)

        # ── Engineered interaction features (same logic used at inference)
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)

        traffic_x_peak        = traffic_code * is_peak
        weather_x_distance    = weather_code * (distance_km / 500.0)
        congestion_x_waiting  = hub_congestion * (waiting_time_est / 60.0)
        temp_x_cargo          = (temperature / 50.0) * (shipment["cargo_code"] == 1)

        route_type_code = 0 if distance_km < 80 else (1 if distance_km < 250 else 2)

        # ── Compute delay probability via latent rules
        base_prob = _compute_delay_probability(
            traffic_code       = traffic_code,
            weather_code       = weather_code,
            is_peak_hour       = is_peak,
            is_weekend         = is_weekend,
            distance_km        = distance_km,
            hub_congestion     = hub_congestion,
            waiting_time_est   = waiting_time_est,
            temperature        = temperature,
            cargo_code         = shipment["cargo_code"],
            vehicle_code       = shipment["vehicle_code"],
            priority_level     = shipment["priority_level"],
            demand_pressure_val = dp,
        )

        # Add noise so no single feature perfectly predicts the label
        noise = float(rng.normal(0, 0.10))
        final_prob = max(0.0, min(1.0, base_prob + noise))

        delayed = int(final_prob >= 0.55)   # ~25-28% target rate
        n_delayed += delayed

        # ── Synthesize Time & Duration Variables for Regression ──────────────
        base_duration = max(0.5, distance_km / 60.0)  # nominal 60 km/h
        traffic_multiplier = 1.0 + (traffic_code * 0.15)
        traffic_time = base_duration * traffic_multiplier + (waiting_time_est / 60.0)
        traffic_delay = traffic_time - base_duration

        if delayed:
            delay_minutes = int(rng.normal(180 * final_prob, 40))
            delay_minutes = max(30, delay_minutes)
        else:
            delay_minutes = int(rng.normal(15 * final_prob, 5))
            delay_minutes = max(0, delay_minutes)

        records.append({
            # Identifiers
            "shipment_id":           i + 1,
            "departure_time":        dep_time.isoformat(),
            "source":                src["city"],
            "destination":           dst["city"],
            # Time features
            "departure_hour":        hour,
            "departure_minute":      minute,
            "day_of_week":           dayofweek,
            "month":                 month,
            "is_weekend":            is_weekend,
            "is_peak_hour":          is_peak,
            "hour_sin":              round(hour_sin, 4),
            "hour_cos":              round(hour_cos, 4),
            # Route features
            "distance_km":           round(distance_km, 1),
            "base_duration":         round(base_duration, 2),
            "traffic_time":          round(traffic_time, 2),
            "traffic_delay":         round(traffic_delay, 2),
            "route_type":            ["city", "regional", "highway"][route_type_code],
            "route_type_code":       route_type_code,
            # Hub features
            "source_hub_type":       src["type"],
            "source_hub_type_code":  HUB_TYPE_CODE[src["type"]],
            "dest_hub_type":         dst["type"],
            "dest_hub_type_code":    HUB_TYPE_CODE[dst["type"]],
            "hub_congestion":        round(hub_congestion, 4),
            # Traffic features
            "traffic_level":         traffic,
            "traffic_code":          traffic_code,
            "waiting_time_est":      round(waiting_time_est, 1),
            "demand_pressure":       round(dp, 4),
            # Weather features
            "weather":               weather,
            "weather_code":          weather_code,
            "temperature":           round(temperature, 1),
            # Shipment features
            "vehicle_type":          shipment["vehicle_type"],
            "vehicle_code":          shipment["vehicle_code"],
            "cargo_type":            shipment["cargo_type"],
            "cargo_code":            shipment["cargo_code"],
            "priority_level":        shipment["priority_level"],
            # Interaction features
            "traffic_x_peak":        traffic_x_peak,
            "weather_x_distance":    round(weather_x_distance, 4),
            "congestion_x_waiting":  round(congestion_x_waiting, 4),
            "temp_x_cargo":          round(temp_x_cargo, 4),
            # Target
            "delay_probability":     round(final_prob, 4),
            "delayed":               delayed,
            "delay_minutes":         delay_minutes,
        })

    df = pd.DataFrame(records)
    rate = n_delayed / n
    print(f"Generated {n:,} shipments | delay rate: {rate:.1%} ({n_delayed:,} delayed)")
    return df


def save_dataset(path: str = OUT_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df = generate_dataset()
    df.to_csv(path, index=False)
    print(f"Saved → {path}")


if __name__ == "__main__":
    save_dataset()
