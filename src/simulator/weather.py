"""
weather.py  —  Weather simulation for training and inference fallback.

During training: weather is sampled probabilistically by season.
During inference: fetched from Visual Crossing Weather API for the specific
departure date/time; if unavailable, falls back to seasonal defaults.
"""

import numpy as np

WEATHER_LEVELS   = ["clear", "rain", "fog", "storm"]
WEATHER_CODE_MAP = {w: i for i, w in enumerate(WEATHER_LEVELS)}

# Cache to avoid repeated API calls — keyed by (city, date, hour)
_weather_cache = {}

# Seasonal weather profiles (North India)
SEASON_PROFILES = {
    "summer":  {"probs": [0.60, 0.05, 0.05, 0.30], "temp_mean": 39.0, "temp_std": 3.5},
    "monsoon": {"probs": [0.20, 0.50, 0.10, 0.20], "temp_mean": 30.0, "temp_std": 2.5},
    "winter":  {"probs": [0.50, 0.10, 0.35, 0.05], "temp_mean": 15.0, "temp_std": 5.0},
}


def _season(month: int) -> str:
    if 3 <= month <= 5:
        return "summer"
    if 6 <= month <= 9:
        return "monsoon"
    return "winter"


def sample_weather(month: int, rng: np.random.Generator) -> tuple[str, float]:
    """
    Sample (weather_level, temperature) for the given month.
    Used during training data generation.
    """
    season = _season(month)
    profile = SEASON_PROFILES[season]
    weather = rng.choice(WEATHER_LEVELS, p=profile["probs"])
    temp = float(rng.normal(profile["temp_mean"], profile["temp_std"]))
    return weather, round(temp, 1)


def default_weather(month: int) -> tuple[str, float]:
    """
    Return the most likely (weather, temperature) for a given month.
    Used as inference fallback when no live API is available.
    Fully deterministic.
    """
    season = _season(month)
    profile = SEASON_PROFILES[season]
    weather = WEATHER_LEVELS[int(np.argmax(profile["probs"]))]
    temp = profile["temp_mean"]
    return weather, temp


def encode_weather(weather_level: str) -> int:
    return WEATHER_CODE_MAP[weather_level]


def _map_conditions(conditions: str) -> str:
    """
    Map Visual Crossing 'conditions' string to our internal weather level.
    Visual Crossing returns values like: 'Clear', 'Partially cloudy',
    'Rain, Overcast', 'Thunderstorms', 'Fog', etc.
    """
    c = conditions.lower()

    if "thunder" in c or "storm" in c:
        return "storm"
    elif "fog" in c or "mist" in c or "haze" in c:
        return "fog"
    elif "rain" in c or "drizzle" in c or "shower" in c:
        return "rain"
    else:
        return "clear"


def try_live_weather(
    city: str,
    api_key: str | None,
    departure_time: str | None = None,
) -> tuple[str | None, float | None]:
    """
    Fetch weather from Visual Crossing Weather API for a specific date and hour.

    Parameters
    ----------
    city           : City name (e.g. "Delhi", "Jaipur")
    api_key        : Visual Crossing API key
    departure_time : ISO 8601 string (e.g. "2026-04-15T14:00:00")
                     If provided, fetches weather for that specific date/hour.
                     If None, fetches current conditions.

    Returns (weather_level, temperature) or (None, None) on failure.
    """
    from datetime import datetime

    # Parse the departure time for cache key and API query
    target_date = None
    target_hour = None
    if departure_time:
        try:
            dt = datetime.fromisoformat(departure_time)
            target_date = dt.strftime("%Y-%m-%d")
            target_hour = dt.hour
        except ValueError:
            pass

    # Build cache key using city + date + hour
    cache_key = f"{city}|{target_date or 'now'}|{target_hour if target_hour is not None else 'now'}"

    if cache_key in _weather_cache:
        print(f"⚡ Using cached weather for: {city} ({target_date} {target_hour}:00)")
        return _weather_cache[cache_key]

    if not api_key:
        if not hasattr(try_live_weather, '_warned'):
            print("⚠️ No weather API key — using simulated weather fallback")
            try_live_weather._warned = True
        return None, None

    # If we've already been rate-limited this session, skip all API calls
    if getattr(try_live_weather, '_rate_limited', False):
        return None, None

    try:
        import requests
        import time

        # Small delay between API calls to avoid rate limiting
        time.sleep(0.2)

        # Build the Visual Crossing API URL
        if target_date:
            print(f"🌍 Fetching weather for: {city} on {target_date} at {target_hour}:00")
            url = (
                f"https://weather.visualcrossing.com/VisualCrossingWebServices"
                f"/rest/services/timeline/{city}/{target_date}/{target_date}"
                f"?unitGroup=metric&key={api_key}&contentType=json"
                f"&include=hours"
            )
        else:
            print(f"🌍 Fetching LIVE weather for: {city}")
            url = (
                f"https://weather.visualcrossing.com/VisualCrossingWebServices"
                f"/rest/services/timeline/{city}"
                f"?unitGroup=metric&key={api_key}&contentType=json"
                f"&include=current"
            )

        r = requests.get(url, timeout=8)

        # Handle rate limiting (429): stop ALL API calls for this session
        if r.status_code == 429:
            print("⚠️ Weather API rate limit reached — switching to simulated fallback for this session")
            try_live_weather._rate_limited = True
            _weather_cache[cache_key] = (None, None)
            return None, None

        r.raise_for_status()
        data = r.json()

        temp = None
        conditions = None

        if target_date and target_hour is not None:
            # Extract the specific hour from the hourly data
            days = data.get("days", [])
            if days:
                hours = days[0].get("hours", [])
                for h in hours:
                    hour_str = h.get("datetime", "")
                    try:
                        h_val = int(hour_str.split(":")[0])
                        if h_val == target_hour:
                            temp = float(h.get("temp", 0))
                            conditions = h.get("conditions", "Clear")
                            break
                    except (ValueError, IndexError):
                        continue

                # Fallback to day-level data if hour not found
                if temp is None:
                    temp = float(days[0].get("temp", 0))
                    conditions = days[0].get("conditions", "Clear")
        else:
            current = data.get("currentConditions")
            if current:
                temp = float(current.get("temp", 0))
                conditions = current.get("conditions", "Clear")

        if temp is None or conditions is None:
            print("❌ Could not extract weather from API response")
            _weather_cache[cache_key] = (None, None)
            return None, None

        weather = _map_conditions(conditions)
        result = (weather, round(temp, 1))

        # Save success to cache
        _weather_cache[cache_key] = result

        print(f"✅ WEATHER: {weather}, {temp}°C ({conditions})")

        return result

    except Exception as e:
        print(f"❌ Weather API failed: {e}")
        # Cache the failure so we don't retry the same city
        _weather_cache[cache_key] = (None, None)
        return None, None