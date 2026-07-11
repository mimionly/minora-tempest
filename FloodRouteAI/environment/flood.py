import requests


BASE = "https://flood-api.open-meteo.com/v1/flood"


def get_river_discharge(lat, lon):

    response = requests.get(

        BASE,

        params={

            "latitude": lat,

            "longitude": lon,

            "daily": "river_discharge"

        },

        timeout=10

    )

    if response.status_code != 200:

        return 0

    data = response.json()

    values = data.get("daily", {}).get("river_discharge", [])

    if len(values) == 0:

        return 0

    return values[0]