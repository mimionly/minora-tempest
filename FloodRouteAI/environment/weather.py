import requests

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather(lat, lon):

    params = {

        "latitude": lat,
        "longitude": lon,

        "current": "temperature_2m,rain",

        "hourly": "precipitation",

        "forecast_days": 1

    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    current_rain = data["current"].get("rain", 0)

    hourly = data["hourly"]["precipitation"][:3]

    rainfall_last_3h = sum(hourly)

    return {

        "current_rain": current_rain,

        "rainfall_3h": rainfall_last_3h

    }