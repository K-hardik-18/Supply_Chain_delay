"""
traffic.py  —  Deterministic + probabilistic traffic simulation.

Traffic is sampled during training (generator.py).
At inference it is deterministically estimated from departure hour alone,
so the same request always produces the same features.
"""

import numpy as np

TRAFFIC_LEVELS   = ["clear", "moderate", "heavy", "severe"]
TRAFFIC_CODE_MAP = {t: i for i, t in enumerate(TRAFFIC_LEVELS)}

# Waiting time (minutes) by traffic level — deterministic means used at inference
WAITING_TIME_MEAN = {"clear": 5, "moderate": 14, "heavy": 28, "severe": 45}
WAITING_TIME_STD  = {"clear": 2, "moderate": 4,  "heavy": 6,  "severe": 8}

PEAK_HOURS = [7, 8, 9, 17, 18, 19]


def _probs_for_hour(hour: int, is_weekend: bool) -> list:
    """Return [clear, moderate, heavy, severe] probabilities for this hour."""
    if is_weekend:
        return [0.55, 0.28, 0.12, 0.05]
    if hour in PEAK_HOURS:
        return [0.10, 0.28, 0.42, 0.20]
    if 10 <= hour <= 16:          # mid-day
        return [0.38, 0.36, 0.18, 0.08]
    return [0.55, 0.30, 0.11, 0.04]  # night/early morning


def sample_traffic(hour: int, is_weekend: bool, rng: np.random.Generator) -> str:
    """Sample a traffic level. Used in the simulator (training data generation)."""
    probs = _probs_for_hour(hour, is_weekend)
    return rng.choice(TRAFFIC_LEVELS, p=probs)


def estimate_traffic(hour: int, is_weekend: bool = False) -> str:
    """
    Deterministic traffic estimate for inference.
    Returns the most-likely traffic level for this hour — no randomness.
    """
    probs = _probs_for_hour(hour, is_weekend)
    return TRAFFIC_LEVELS[int(np.argmax(probs))]


def expected_traffic_code(hour: int, is_weekend: bool = False) -> float:
    """
    Expected traffic code as a continuous float, matching the training distribution.

    At training, traffic_code is randomly sampled so at 2pm it can be 0,1,2,3.
    Argmax always returns 0 (clear) at 2pm — a value the model rarely saw alone
    for that hour during training. This is training/serving skew.

    Expected value fixes it:
      2pm off-peak: 0.38*0 + 0.36*1 + 0.18*2 + 0.08*3 = 0.96
      8am peak:     0.10*0 + 0.28*1 + 0.42*2 + 0.20*3 = 1.72
      Night (1am):  0.55*0 + 0.30*1 + 0.11*2 + 0.04*3 = 0.64

    XGBoost handles float inputs correctly via continuous split thresholds.
    """
    probs = _probs_for_hour(hour, is_weekend)
    return float(sum(code * prob for code, prob in enumerate(probs)))


def waiting_time_for(traffic_level: str) -> float:
    """Deterministic waiting time estimate (minutes) for inference."""
    return float(WAITING_TIME_MEAN[traffic_level])


def encode_traffic(traffic_level: str) -> int:
    return TRAFFIC_CODE_MAP[traffic_level]


def hub_congestion_for(demand_pressure_val: float, capacity: int) -> float:
    """
    Compute hub congestion from demand pressure and hub capacity.
    Smaller hubs are more sensitive to demand, but never clamp to 1.0
    deterministically — that removes useful signal from the model.
    Uses a soft sigmoid-like scaling instead of a hard min().
    """
    capacity_ratio = capacity / 500.0          # 1.0 = Delhi (max), 0.2 = Bikaner
    sensitivity    = 1.0 + 0.5 * (1 - capacity_ratio)   # small hubs: up to 1.5x sensitive
    raw = demand_pressure_val * sensitivity
    # Soft cap via tanh so values approach 1.0 asymptotically
    import math
    return round(math.tanh(raw * 1.1), 4)


def demand_pressure(hour: int) -> float:
    """
    Normalised demand pressure [0, 1] based on hour of day.
    Peak demand: morning (9-11am) and evening (4-7pm).
    Fully deterministic — same hour always gives same value.
    """
    demand = {
        0: 0.18, 1: 0.12, 2: 0.10, 3: 0.10, 4: 0.12, 5: 0.20,
        6: 0.35, 7: 0.60, 8: 0.78, 9: 0.85, 10: 0.82, 11: 0.75,
        12: 0.65, 13: 0.70, 14: 0.72, 15: 0.75, 16: 0.82, 17: 0.90,
        18: 0.88, 19: 0.80, 20: 0.65, 21: 0.50, 22: 0.38, 23: 0.25,
    }
    return demand[hour % 24]
