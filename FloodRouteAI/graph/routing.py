import networkx as nx
import graph.graph_store as store
import time
from data.vehicles import VEHICLES

from math import radians
from math import sin
from math import cos
from math import sqrt
from math import atan2


EARTH_RADIUS = 6371


def haversine(node1, node2):

    G = store.graph

    lat1 = radians(G.nodes[node1]["y"])
    lon1 = radians(G.nodes[node1]["x"])

    lat2 = radians(G.nodes[node2]["y"])
    lon2 = radians(G.nodes[node2]["x"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2

    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return EARTH_RADIUS * c


def heuristic(a, b):

    distance = haversine(a, b)

    return (distance / 30) * 60


def edge_cost(u, v, data, vehicle):

    vehicle_info = VEHICLES[vehicle]

    clearance = vehicle_info["clearance"]

    if data["depth"] > clearance:

        return float("inf")

    cost = data["travel_time"]

    cost += data["risk"] * 20

    if data["road_condition"] == "WET":

        cost += 5

    elif data["road_condition"] == "FLOODED":

        cost += 50

    elif data["road_condition"] == "BLOCKED":

        return float("inf")

    return cost


def find_route(start_node, end_node, vehicle="ambulance"):

    G = store.graph

    start = time.perf_counter()

    path = nx.astar_path(

        G,

        start_node,

        end_node,

        heuristic=heuristic,

        weight=lambda u, v, d: edge_cost(u, v, d, vehicle)

    )

    total_distance = 0

    total_time = 0

    total_risk = 0

    for i in range(len(path)-1):

        edge = G[path[i]][path[i+1]][0]

        total_distance += edge.get("length", 0)

        total_time += edge.get("travel_time", 0)

        total_risk += edge.get("risk", 0)

    elapsed = (time.perf_counter()-start)*1000

    return {

        "vehicle": vehicle,

        "path": path,

        "distance_m": round(total_distance),

        "travel_time_min": round(total_time,2),

        "average_risk": round(total_risk/max(len(path)-1,1),3),

        "calculation_ms": round(elapsed,2)

    }