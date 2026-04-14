"""
googlemaps_api.py  —  Google Maps Directions API integration for real road routing.

Provides exact distance, travel time, and polyline decoding to GeoJSON.
"""

import googlemaps
from functools import lru_cache

# Dictionary to hold the client instance so we don't recreate it every call
_clients = {}

def get_client(api_key: str):
    if api_key not in _clients:
        _clients[api_key] = googlemaps.Client(key=api_key)
    return _clients[api_key]


@lru_cache(maxsize=1024)
def get_gmaps_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, api_key: str) -> tuple[float | None, float | None, dict | None]:
    """
    Get real road distance, travel time, and GeoJSON geometry from Google Maps Directions API.
    
    Returns
    -------
    (distance_km, duration_hr, geometry_dict)
    Returns (None, None, None) on failure.
    """
    if not api_key:
        print("[GoogleMaps] No API key provided.")
        return None, None, None

    try:
        gmaps = get_client(api_key)
        
        # Request directions
        origin = f"{origin_lat},{origin_lon}"
        destination = f"{dest_lat},{dest_lon}"
        
        routes = gmaps.directions(origin, destination, mode="driving")
        
        if routes:
            route = routes[0]
            leg = route["legs"][0]
            
            # Distance in meters -> km
            distance_km = round(leg["distance"]["value"] / 1000.0, 2)
            
            # Duration in seconds -> hr
            duration_hr = round(leg["duration"]["value"] / 3600.0, 2)
            
            # Decode overview_polyline for map rendering
            overview_polyline = route["overview_polyline"]["points"]
            from googlemaps.convert import decode_polyline
            decoded = decode_polyline(overview_polyline)
            
            # Convert to GeoJSON LineString coordinates: [lon, lat]
            # googlemaps returns list of {'lat': float, 'lng': float}
            coords = [[point['lng'], point['lat']] for point in decoded]
            
            geometry = {
                "type": "LineString",
                "coordinates": coords
            }
            
            return distance_km, duration_hr, geometry
            
    except Exception as e:
        print(f"[GoogleMaps] API call failed: {e}")
        
    return None, None, None
