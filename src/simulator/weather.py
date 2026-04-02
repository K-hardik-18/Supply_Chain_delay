"""
weather.py  —  Weather simulation for training and inference fallback.

During training: weather is sampled probabilistically by season.
During inference: optionally fetched from live API; if unavailable,
falls back to seasonal defaults. NEVER random — always deterministic fallback.
"""

import numpy as np

WEATHER_LEVELS   = ["clear", "rain", "fog", "storm"]
WEATHER_CODE_MAP = {w: i for i, w in enumerate(WEATHER_LEVELS)}

# 🌟 NEW: Cache to avoid repeated API calls
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


def try_live_weather(city: str, api_key: str | None) -> tuple[str | None, float | None]:
    """
    Attempt to fetch weather from OpenWeatherMap.
    Uses caching to avoid repeated API calls.
    Returns (None, None) on failure.
    """

    # 🌟 NEW: Check cache first
    if city in _weather_cache:
        print(f"⚡ Using cached weather for: {city}")
        return _weather_cache[city]

    if not api_key:
        if not hasattr(try_live_weather, '_warned'):
            print("⚠️ No weather API key — using simulated weather fallback")
            try_live_weather._warned = True
        return None, None

    try:
        import requests

        print(f"🌍 Fetching LIVE weather for: {city}")

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={api_key}&units=metric"
        )

        r = requests.get(url, timeout=3).json()

        # 🌟 NEW: Handle API errors properly
        if "main" not in r or "weather" not in r:
            print("❌ Invalid API response:", r)
            return None, None

        temp = float(r["main"]["temp"])
        desc = r["weather"][0]["main"].lower()

        if "storm" in desc or "thunder" in desc:
            weather = "storm"
        elif "fog" in desc or "mist" in desc or "haze" in desc:
            weather = "fog"
        elif "rain" in desc or "drizzle" in desc:
            weather = "rain"
        else:
            weather = "clear"

        result = (weather, round(temp, 1))

        # 🌟 NEW: Save to cache
        _weather_cache[city] = result

        print(f"✅ LIVE WEATHER: {weather}, {temp}")

        return result

    except Exception as e:
        print("❌ Weather API failed:", e)
        return None, None