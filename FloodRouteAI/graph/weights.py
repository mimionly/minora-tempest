import graph.graph_store as store

DEFAULT_SPEED = 30  # km/h


def initialize_edge_weights():

    G = store.graph

    print("Initializing edge weights...")

    for u, v, key, data in G.edges(keys=True, data=True):

        length = data.get("length", 0)

        speed = DEFAULT_SPEED

        if "maxspeed" in data:

            try:

                speed = float(str(data["maxspeed"]).split()[0])

            except:

                pass

        travel_time = (length / 1000) / speed * 60

        data["travel_time"] = travel_time

        data["risk"] = 0.0

        data["blocked"] = False

        data["depth"] = 0

        data["road_condition"] = "SAFE"

    print("Edge weights ready.")