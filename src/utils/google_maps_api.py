"""
google_maps_api.py  —  Google Maps Distance Matrix API client.

Returns real road distance (km) and estimated travel time (hours)
between two lat/lon coordinates.

Falls back gracefully — returns (None, None) on failure,
so callers can use haversine as fallback.
"""

import requests
from functools import lru_cache

# Cache to avoid repeated API calls for the same origin/destination
_distance_cache: dict[tuple, tuple] = {}


def get_distance_and_time(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    api_key: str,
) -> tuple[float | None, float | None]:
    """
    Query Google Maps Distance Matrix API for driving distance and duration.

    Returns
    -------
    (distance_km, duration_hr) or (None, None) on failure.
    """

    cache_key = (round(origin_lat, 4), round(origin_lon, 4),
                 round(dest_lat, 4), round(dest_lon, 4))

    if cache_key in _distance_cache:
        return _distance_cache[cache_key]

    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{origin_lat},{origin_lon}",
            "destinations": f"{dest_lat},{dest_lon}",
            "key": api_key,
            "mode": "driving",
            "units": "metric",
        }

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data.get("status") != "OK":
            print(f"⚠️ Google Maps API error: {data.get('status')}")
            return None, None

        element = data["rows"][0]["elements"][0]

        if element.get("status") != "OK":
            print(f"⚠️ Google Maps element error: {element.get('status')}")
            return None, None

        distance_m  = element["distance"]["value"]       # meters
        duration_s  = element["duration"]["value"]        # seconds

        distance_km = round(distance_m / 1000.0, 1)
        duration_hr = round(duration_s / 3600.0, 2)

        result = (distance_km, duration_hr)
        _distance_cache[cache_key] = result

        print(f"✅ Google Maps: {distance_km} km, {duration_hr} hr")
        return result

    except Exception as e:
        print(f"❌ Google Maps API failed: {e}")
        return None, None


def clear_cache():
    """Clear the distance cache (useful for testing)."""
    _distance_cache.clear()
