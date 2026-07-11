import graph.graph_store as store

from environment.weather import get_weather

from environment.elevation import get_elevation

from environment.flood import get_river_discharge

from engines.risk_engine import calculate_risk

import threading

import time


def update_graph():

    G = store.graph

    print("Updating environmental conditions...")

    for node in list(G.nodes())[:300]:

        lat = G.nodes[node]["y"]

        lon = G.nodes[node]["x"]

        try:

            weather = get_weather(lat, lon)

            elevation = get_elevation(lat, lon)

            discharge = get_river_discharge(lat, lon)

            risk = calculate_risk(

                weather["rainfall_3h"],

                discharge,

                elevation,

                200
            )

            for neighbor in G.neighbors(node):

                edge = G[node][neighbor][0]

                edge["risk"] = risk

        except Exception as e:

            print(e)

    print("Graph Updated")


def background_monitor():

    while True:

        update_graph()

        time.sleep(300)


def start_monitor():

    thread = threading.Thread(

        target=background_monitor,

        daemon=True

    )

    thread.start()