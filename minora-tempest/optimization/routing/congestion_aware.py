"""
Congestion-Aware Routing
=========================

Routes that consider current traffic load on edges.
When an evacuation route is assigned, the roads on that path
get "heavier" — forcing subsequent routes to spread out.

This prevents the classic disaster scenario:
"Everyone evacuates on the same road → total gridlock."
"""

from typing import Optional

import networkx as nx

from optimization.types import RouteResult, NodeId
from optimization.routing.safe_route import find_safe_route


# How much congestion each assigned route adds to its edges
CONGESTION_INCREMENT = 0.15

# Maximum congestion before road is effectively unusable
MAX_CONGESTION = 0.95


def apply_route_congestion(graph: nx.Graph, route: RouteResult) -> None:
    """
    After a route is assigned to a resource, increase congestion
    on all edges along that route.

    This forces the NEXT routing call to consider alternative roads.

    Mutates the graph in-place (Person 1's graph).
    """
    for i in range(len(route.path_nodes) - 1):
        u, v = route.path_nodes[i], route.path_nodes[i + 1]

        if graph.has_edge(u, v):
            edge_data = graph[u][v]

            # Handle multigraph
            if isinstance(edge_data, dict) and 0 in edge_data:
                edge_data = edge_data[0]

            current = edge_data.get("congestion", 0.0)
            edge_data["congestion"] = min(current + CONGESTION_INCREMENT, MAX_CONGESTION)


def clear_route_congestion(graph: nx.Graph, route: RouteResult) -> None:
    """
    When a resource completes its route or is reassigned,
    reduce congestion on the old route edges.
    """
    for i in range(len(route.path_nodes) - 1):
        u, v = route.path_nodes[i], route.path_nodes[i + 1]

        if graph.has_edge(u, v):
            edge_data = graph[u][v]

            if isinstance(edge_data, dict) and 0 in edge_data:
                edge_data = edge_data[0]

            current = edge_data.get("congestion", 0.0)
            edge_data["congestion"] = max(current - CONGESTION_INCREMENT, 0.0)


def find_congestion_aware_route(
    graph: nx.Graph,
    source: NodeId,
    target: NodeId,
    auto_apply_congestion: bool = True,
) -> Optional[RouteResult]:
    """
    Find a safe route AND automatically register it as "in use"
    so the next vehicle will avoid the same roads.

    Args:
        graph:                  City graph
        source:                 Start node
        target:                 Destination node
        auto_apply_congestion:  If True, mark the route edges as congested

    Returns:
        RouteResult or None.
    """
    route = find_safe_route(
        graph, source, target,
        congestion_penalty=3.0,  # higher than default to spread traffic
    )

    if route is not None and auto_apply_congestion:
        apply_route_congestion(graph, route)

    return route
