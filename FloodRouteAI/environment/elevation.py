import requests


def get_elevation(lat, lon):

    url = "https://api.open-elevation.com/api/v1/lookup"

    response = requests.get(

        url,

        params={

            "locations": f"{lat},{lon}"

        },

        timeout=10

    )

    response.raise_for_status()

    data = response.json()

    return data["results"][0]["elevation"]