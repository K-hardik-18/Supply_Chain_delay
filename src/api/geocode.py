"""
geocode.py  —  Connects to OpenStreetMap (Photon API) to convert place names to GPS coordinates dynamically.
"""
import requests
import urllib.parse
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Photon is a free, high-performance geocoding API based on OpenStreetMap data (Komoot).
# It does not require API keys for light to moderate use.
PHOTON_API_URL = "https://photon.komoot.io/api/"

@router.get("/geocode", tags=["Data"])
def geocode_place(q: str):
    """
    Search for a place in India and return its latitude/longitude coordinates.
    Provides autocomplete suggestions to the frontend.
    """
    if not q or len(q.strip()) < 2:
        return {"suggestions": []}
        
    query = urllib.parse.quote(q)
    
    # Restrict to India (lat/lon bounding box or geographic bias)
    # 22, 79 is roughly central India.
    url = f"{PHOTON_API_URL}?q={query}&lat=22&lon=79&limit=5"
    
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        suggestions = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [])
            
            if not coords or len(coords) < 2:
                continue
                
            # Filter geographically slightly if needed, but photon handles generic well.
            # Usually country is in props
            country = props.get("country")
            if country and country.lower() not in ["india", "ind"]:
                continue # Soft-restrict to India
                
            # Construct a readable display name
            name_parts = []
            if props.get("name"): name_parts.append(props["name"])
            if props.get("city"): name_parts.append(props["city"])
            elif props.get("county"): name_parts.append(props["county"])
            if props.get("state"): name_parts.append(props["state"])
            
            # Remove duplicates while preserving order
            seen = set()
            unique_parts = [x for x in name_parts if not (x in seen or seen.add(x))]
            display_name = ", ".join(unique_parts)
            
            if not display_name:
                display_name = "Unknown Location"
                
            suggestions.append({
                "name": f"{display_name}, India",
                "lat": coords[1],
                "lon": coords[0],
                "type": props.get("osm_value", "place")
            })
            
        return {"suggestions": suggestions}
        
    except requests.RequestException as e:
        # Fallback to empty if Photon is down or rate limited (it rarely happens for light requests)
        print(f"[Geocode Error] {e}")
        return {"suggestions": []}
