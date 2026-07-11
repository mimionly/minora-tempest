from flask import Blueprint
from flask import jsonify
from graph.routing import find_route
import osmnx as ox
from flask import request

import graph.graph_store as store

@route_api.route("/route")

def route():

    G = store.graph

    start_lat = float(request.args["start_lat"])
    start_lon = float(request.args["start_lon"])

    end_lat = float(request.args["end_lat"])
    end_lon = float(request.args["end_lon"])

    start_node = ox.distance.nearest_nodes(
        G,
        start_lon,
        start_lat
    )

    end_node = ox.distance.nearest_nodes(
        G,
        end_lon,
        end_lat
    )

    vehicle = request.args.get(

    "vehicle",

    "ambulance"

)

result = find_route(

    start_node,

    end_node,

    vehicle

)

    return jsonify(result)

route_api = Blueprint(
    "route_api",
    __name__
)


@route_api.route("/graph-info")
def graph_info():

    G = store.graph

    return jsonify({

        "nodes": len(G.nodes),

        "edges": len(G.edges)

    })


@route_api.route("/health")
def health():

    return jsonify({

        "status": "running"

    })