def normalize(value, maximum):

    return min(value / maximum, 1)


def calculate_risk(

    rainfall,

    discharge,

    elevation,

    water_distance

):

    rainfall_factor = normalize(rainfall, 50)

    discharge_factor = normalize(discharge, 1000)

    elevation_factor = 1 - normalize(elevation, 100)

    proximity_factor = 1 - normalize(water_distance, 500)

    risk = (

        rainfall_factor * 0.35 +

        discharge_factor * 0.25 +

        elevation_factor * 0.20 +

        proximity_factor * 0.20

    )

    return round(risk, 3)