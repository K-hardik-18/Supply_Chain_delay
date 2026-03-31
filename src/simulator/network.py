"""
network.py  —  Builds directed edges between hubs within range.

Run directly to (re)generate data/network.csv:
    python -m src.simulator.network
"""

import math
import pandas as pd
from pathlib import Path
from itertools import combinations

from .hubs import HUBS, get_hub_df

# Max distance (km) to create an edge between two hubs.
# Set to 9999 so every hub connects to every other hub (fully connected graph for VRP).
MAX_EDGE_KM = 9999

# Road-type classification by distance
def _road_type(dist_km: float) -> str:
    if dist_km < 80:
        return "city"
    elif dist_km < 250:
        return "regional"
    else:
        return "highway"

ROAD_TYPE_CODE = {"city": 0, "regional": 1, "highway": 2}

# Base speed (km/h) per road type — used for travel time estimate
BASE_SPEED = {"city": 35, "regional": 55, "highway": 75}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two lat/lon points."""
    R = 6371
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_network() -> pd.DataFrame:
    """
    Create directed edges for every hub pair within MAX_EDGE_KM.
    Each edge is bidirectional (A→B and B→A recorded separately).
    """
    records = []

    for h1, h2 in combinations(HUBS, 2):
        dist = haversine(h1["lat"], h1["lon"], h2["lat"], h2["lon"])

        if dist > MAX_EDGE_KM:
            continue

        rt = _road_type(dist)
        speed = BASE_SPEED[rt]
        base_time = round(dist / speed, 2)          # hours
        rt_code = ROAD_TYPE_CODE[rt]

        # Add both directions
        for src, dst in [(h1, h2), (h2, h1)]:
            records.append({
                "source":          src["city"],
                "destination":     dst["city"],
                "distance_km":     round(dist, 1),
                "base_time_hr":    base_time,
                "road_type":       rt,
                "road_type_code":  rt_code,
                "src_lat":         src["lat"],
                "src_lon":         src["lon"],
                "dst_lat":         dst["lat"],
                "dst_lon":         dst["lon"],
            })

    return pd.DataFrame(records)


def save_network_csv(path: str = "data/network.csv"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df = build_network()
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} directed edges → {path}")
    print(f"Unique hubs in network: {sorted(set(df.source.tolist() + df.destination.tolist()))}")


if __name__ == "__main__":
    save_network_csv()
