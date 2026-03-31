"""
shipments.py  —  Shipment profile definitions and samplers.
"""

import numpy as np

VEHICLE_TYPES = ["bike", "van", "truck"]
VEHICLE_WEIGHTS = [0.15, 0.35, 0.50]
VEHICLE_CODE = {v: i for i, v in enumerate(VEHICLE_TYPES)}

CARGO_TYPES = ["standard", "perishable", "fragile"]
CARGO_WEIGHTS = [0.55, 0.25, 0.20]
CARGO_CODE = {c: i for i, c in enumerate(CARGO_TYPES)}

PRIORITY_LEVELS = [1, 2, 3]
PRIORITY_WEIGHTS = [0.40, 0.40, 0.20]


def sample_shipment(rng: np.random.Generator) -> dict:
    vehicle = rng.choice(VEHICLE_TYPES, p=VEHICLE_WEIGHTS)
    cargo = rng.choice(CARGO_TYPES, p=CARGO_WEIGHTS)
    priority = int(rng.choice(PRIORITY_LEVELS, p=PRIORITY_WEIGHTS))
    return {
        "vehicle_type":  vehicle,
        "vehicle_code":  VEHICLE_CODE[vehicle],
        "cargo_type":    cargo,
        "cargo_code":    CARGO_CODE[cargo],
        "priority_level": priority,
    }


def encode_vehicle(vehicle_type: str) -> int:
    return VEHICLE_CODE[vehicle_type.lower().strip()]


def encode_cargo(cargo_type: str) -> int:
    return CARGO_CODE[cargo_type.lower().strip()]
