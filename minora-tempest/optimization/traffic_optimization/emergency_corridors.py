"""
Emergency Corridors — Priority Road Reservation
=================================================

Creates "emergency corridors" by heavily penalizing civilian
use of roads designated for ambulance/rescue movement.

When an emergency corridor is active:
    - Civilian routing avoids those roads (high penalty)
    - Emergency vehicles get near-zero congestion on them
    - The corridor appears highlighted on the frontend map

This is the "green wave" concept used in real cities.
"""

from typing import List, Set

import networkx as nx

from optimization.types import RouteResult, NodeId


# Penalty applied to corridor edges for civilian routing
CORRIDOR_CIVILIAN_PENALTY = 50.0

# Tag used to mark corridor edges
CORRIDOR_TAG = "emergency_corridor"


def create_emergency_corridor(
    graph: nx.Graph,
    route: RouteResult,
) -> List[tuple]:
    """
    Designate a route as an emergency corridor.

    Marks all edges along the route with high civilian penalty
    and near-zero congestion for emergency vehicles.

    Args:
        graph:  City graph
        route:  The route to designate as corridor

    Returns:
        List of (u, v) edge tuples that form the corridor.
    """
    corridor_edges = []

    for i in range(len(route.path_nodes) - 1):
        u, v = route.path_nodes[i], route.path_nodes[i + 1]

        if not graph.has_edge(u, v):
            continue

        edge_data = graph[u][v]
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        # Mark as emergency corridor
        edge_data[CORRIDOR_TAG] = True

        # Reduce congestion for emergency vehicles
        edge_data["congestion"] = 0.0

        # Add civilian penalty (civilians should avoid this road)
        edge_data["civilian_penalty"] = CORRIDOR_CIVILIAN_PENALTY

        corridor_edges.append((u, v))

    return corridor_edges


def release_emergency_corridor(
    graph: nx.Graph,
    corridor_edges: List[tuple],
) -> None:
    """
    Release an emergency corridor, restoring normal traffic flow.

    Call this when the emergency vehicle has passed through
    or the corridor is no longer needed.
    """
    for u, v in corridor_edges:
        if not graph.has_edge(u, v):
            continue

        edge_data = graph[u][v]
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        edge_data[CORRIDOR_TAG] = False
        edge_data["civilian_penalty"] = 0.0


def get_active_corridors(graph: nx.Graph) -> List[tuple]:
    """Return all edges currently designated as emergency corridors."""
    corridors = []

    for u, v, data in graph.edges(data=True):
        edge_data = data
        if isinstance(data, dict) and 0 in data:
            edge_data = data[0]

        if edge_data.get(CORRIDOR_TAG, False):
            corridors.append((u, v))

    return corridors
