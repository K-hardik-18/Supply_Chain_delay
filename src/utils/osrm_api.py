"""
osrm_api.py  —  Free public OSRM API integration for real road routing.

Replaces Google Maps API for distance, time, and exact road geometry.
OSRM Public API requires NO API KEY, but requires a valid User-Agent.
"""

import requests
import time
from functools import lru_cache

# OSRM Public API endpoint
OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

# We must use a valid User-Agent per OSRM public API policy
HEADERS = {
    "User-Agent": "SmartLogisticsIntelligence/3.0 (Contact: demo@example.com)"
}

@lru_cache(maxsize=1024)
def get_osrm_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> tuple[float | None, float | None, dict | None]:
    """
    Get real road distance, travel time, and GeoJSON geometry from free OSRM API.
    
    Returns
    -------
    (distance_km, duration_hr, geometry_dict)
    Returns (None, None, None) on failure.
    """
    # OSRM expects coordinates as lon,lat
    url = f"{OSRM_BASE_URL}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    
    params = {
        "overview": "full",
        "geometries": "geojson"
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            
            # Distance is in meters -> convert to km
            distance_km = round(route["distance"] / 1000.0, 2)
            
            # Duration is in seconds -> convert to hours
            duration_hr = round(route["duration"] / 3600.0, 2)
            
            # GeoJSON geometry
            geometry = route["geometry"]
            
            # Rate limit compliance (OSRM public API requires no more than 1 req/sec ideally, 
            # though we are making small bursts, a tiny sleep helps avoid 429 Too Many Requests)
            time.sleep(0.1)

            return distance_km, duration_hr, geometry

    except Exception as e:
        print(f"[OSRM] API call failed: {e}")
        
    return None, None, None
