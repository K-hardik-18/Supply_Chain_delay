"""
hubs.py  —  Defines the 20-hub logistics network for Northern India.

Run directly to (re)generate data/hubs.csv:
    python -m src.simulator.hubs
"""

import os
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# HUB DEFINITIONS
# Each hub: name, lat, lon, type, capacity (max shipments/day)
# Types: city | warehouse | distribution | airport
# ---------------------------------------------------------------------------

HUBS = [
    # North
    {"city": "Jaipur",      "lat": 26.9124, "lon": 75.7873, "type": "hub", "capacity": 200},
    {"city": "Delhi",       "lat": 28.6139, "lon": 77.2090, "type": "hub",       "capacity": 500},
    {"city": "Agra",        "lat": 27.1767, "lon": 78.0081, "type": "warehouse",     "capacity": 180},
    {"city": "Ajmer",       "lat": 26.4499, "lon": 74.6399, "type": "hub",          "capacity": 120},
    {"city": "Noida",       "lat": 28.5355, "lon": 77.3910, "type": "warehouse",     "capacity": 220},
    {"city": "Gurgaon",     "lat": 28.4595, "lon": 77.0266, "type": "hub",  "capacity": 250},
    {"city": "Lucknow",     "lat": 26.8467, "lon": 80.9462, "type": "hub",  "capacity": 300},
    {"city": "Kanpur",      "lat": 26.4499, "lon": 80.3319, "type": "warehouse",     "capacity": 200},
    {"city": "Varanasi",    "lat": 25.3176, "lon": 82.9739, "type": "hub",          "capacity": 150},
    {"city": "Prayagraj",   "lat": 25.4358, "lon": 81.8463, "type": "hub",          "capacity": 140},
    {"city": "Jodhpur",     "lat": 26.2389, "lon": 73.0243, "type": "hub",  "capacity": 180},
    {"city": "Udaipur",     "lat": 24.5854, "lon": 73.7125, "type": "hub",          "capacity": 130},
    {"city": "Kota",        "lat": 25.2138, "lon": 75.8648, "type": "warehouse",     "capacity": 160},
    {"city": "Bikaner",     "lat": 28.0229, "lon": 73.3119, "type": "hub",          "capacity": 100},
    {"city": "Mathura",     "lat": 27.4924, "lon": 77.6737, "type": "hub",          "capacity": 140},
    {"city": "Meerut",      "lat": 28.9845, "lon": 77.7064, "type": "hub",          "capacity": 160},
    {"city": "Haridwar",    "lat": 29.9457, "lon": 78.1642, "type": "warehouse",     "capacity": 120},
    {"city": "Chandigarh",  "lat": 30.7333, "lon": 76.7794, "type": "hub",  "capacity": 200},
    {"city": "Amritsar",    "lat": 31.6340, "lon": 74.8723, "type": "hub",       "capacity": 180},
    {"city": "Ludhiana",    "lat": 30.9010, "lon": 75.8573, "type": "warehouse",     "capacity": 220},

    # West (New)
    {"city": "Mumbai",      "lat": 19.0760, "lon": 72.8777, "type": "hub",       "capacity": 600},
    {"city": "Pune",        "lat": 18.5204, "lon": 73.8567, "type": "hub",  "capacity": 350},
    {"city": "Nashik",      "lat": 20.0006, "lon": 73.7828, "type": "warehouse",     "capacity": 180},
    {"city": "Nagpur",      "lat": 21.1458, "lon": 79.0882, "type": "hub",  "capacity": 250},
    {"city": "Ahmedabad",   "lat": 23.0225, "lon": 72.5714, "type": "hub",       "capacity": 400},
    {"city": "Surat",       "lat": 21.1702, "lon": 72.8311, "type": "warehouse",     "capacity": 300},
    {"city": "Vadodara",    "lat": 22.3072, "lon": 73.1812, "type": "hub",          "capacity": 150},
    {"city": "Rajkot",      "lat": 22.3039, "lon": 70.8022, "type": "hub",          "capacity": 120},
    {"city": "Indore",      "lat": 22.7196, "lon": 75.8577, "type": "hub",  "capacity": 280},
    {"city": "Bhopal",      "lat": 23.2599, "lon": 77.4126, "type": "warehouse",     "capacity": 200},

    # South (New)
    {"city": "Bangalore",   "lat": 12.9716, "lon": 77.5946, "type": "hub",       "capacity": 550},
    {"city": "Chennai",     "lat": 13.0827, "lon": 80.2707, "type": "hub",       "capacity": 500},
    {"city": "Hyderabad",   "lat": 17.3850, "lon": 78.4867, "type": "hub",       "capacity": 450},
    {"city": "Kochi",       "lat": 9.9312,  "lon": 76.2673, "type": "warehouse",     "capacity": 180},
    {"city": "Coimbatore",  "lat": 11.0168, "lon": 76.9558, "type": "hub",  "capacity": 220},

    # East (New)
    {"city": "Kolkata",     "lat": 22.5726, "lon": 88.3639, "type": "hub",       "capacity": 480},
    {"city": "Patna",       "lat": 25.5941, "lon": 85.1376, "type": "hub",  "capacity": 250},
    {"city": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245, "type": "warehouse",     "capacity": 190},
    {"city": "Guwahati",    "lat": 26.1445, "lon": 91.7362, "type": "hub",  "capacity": 210},
    {"city": "Ranchi",      "lat": 23.3441, "lon": 85.3096, "type": "hub",          "capacity": 130},
]

# Numeric encoding for hub type
HUB_TYPE_CODE = {
    "warehouse": 0,
    "hub": 1,
}

CITY_NAMES = [h["city"] for h in HUBS]


def get_hub_df() -> pd.DataFrame:
    """Return hub definitions as a DataFrame."""
    df = pd.DataFrame(HUBS)
    df["type_code"] = df["type"].map(HUB_TYPE_CODE)
    return df


def get_hub(city: str) -> dict:
    """Look up a single hub by city name (case-insensitive)."""
    name = city.strip().title()
    for h in HUBS:
        if h["city"].lower() == name.lower():
            return h
    raise ValueError(f"Hub not found: '{city}'. Available: {CITY_NAMES}")


def save_hubs_csv(path: str = "data/hubs.csv"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df = get_hub_df()
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} hubs → {path}")


if __name__ == "__main__":
    save_hubs_csv()
