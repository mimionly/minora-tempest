"""
openweather_loader.py
---------------------
Fetches current weather from the OpenWeather API and normalizes it for wildfire/agent integration.
"""

import json
import urllib.parse
import urllib.request
from typing import Dict, Optional


def get_openweather_current(
    lat: float,
    lon: float,
    api_key: str,
    units: str = "metric",
    timeout: int = 20,
) -> Dict[str, Optional[float]]:
    """Fetch current weather for a coordinate from OpenWeather."""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": units,
    }
    url = f"https://api.openweathermap.org/data/2.5/weather?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = json.load(response)

    weather = data.get("weather", [])
    main = data.get("main", {})
    wind = data.get("wind", {})

    return {
        "latitude": lat,
        "longitude": lon,
        "temperature_c": main.get("temp"),
        "humidity_pct": main.get("humidity"),
        "pressure_hpa": main.get("pressure"),
        "wind_speed_ms": wind.get("speed"),
        "wind_deg": wind.get("deg"),
        "rain_1h_mm": data.get("rain", {}).get("1h", 0.0),
        "snow_1h_mm": data.get("snow", {}).get("1h", 0.0),
        "weather_main": weather[0].get("main") if weather else None,
        "weather_description": weather[0].get("description") if weather else None,
    }


def enrich_fire_points_with_weather(
    fire_points: list[Dict],
    api_key: str,
    max_points: int = 50,
) -> list[Dict]:
    """Attach OpenWeather data to each fire point for agent input."""
    enriched = []
    for fp in fire_points[:max_points]:
        weather = get_openweather_current(
            fp["latitude"],
            fp["longitude"],
            api_key,
        )
        enriched.append({"fire": fp, "weather": weather})
    return enriched
