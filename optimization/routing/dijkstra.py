"""
Dijkstra Routing Algorithm — Guaranteed Shortest Safe Path
==========================================================

Unlike A* (which uses a heuristic for speed), Dijkstra guarantees
the mathematically optimal path. Use this as a FALLBACK when:

1. A* fails (heuristic issues on unusual graph topologies)
2. You need provably optimal paths for judge cross-questions
3. Comparing A* results for validation

Uses the same dynamic cost function as astar.py.
"""

from typing import Optional, Callable

import networkx as nx

from optimization.types import RouteResult, NodeId
from optimization.routing.astar import (
    make_cost_function,
    DEFAULT_RISK_PENALTY,
    DEFAULT_CONGESTION_PENALTY,
    DEFAULT_SPEED_KPH,
)


def _extract_route_result_dijkstra(
    graph: nx.Graph,
    path_nodes: list,
    cost_fn: Callable,
) -> RouteResult:
    """Extract route metadata for a Dijkstra-computed path."""
    path_coords = []
    total_distance = 0.0
    total_cost = 0.0
    total_risk = 0.0
    total_time = 0.0

    for node in path_nodes:
        data = graph.nodes[node]
        path_coords.append((data.get("y", 0.0), data.get("x", 0.0)))

    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        edge_data = graph[u][v]

        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        length = edge_data.get("length", 100.0)
        total_distance += length
        total_cost += cost_fn(u, v, edge_data)
        total_risk += edge_data.get("disaster_risk", 0.0)

        speed_kph = edge_data.get("speed_kph", DEFAULT_SPEED_KPH)
        if speed_kph <= 0:
            speed_kph = DEFAULT_SPEED_KPH
        total_time += (length / 1000.0) / speed_kph * 3600

    num_edges = max(len(path_nodes) - 1, 1)

    return RouteResult(
        path_nodes=path_nodes,
        path_coords=path_coords,
        total_distance_m=total_distance,
        total_cost=total_cost,
        estimated_time_s=total_time,
        risk_score=total_risk / num_edges,
        algorithm="dijkstra",
        is_fallback=False,
    )


def find_safest_path_dijkstra(
    graph: nx.Graph,
    source_node: NodeId,
    target_node: NodeId,
    risk_penalty: float = DEFAULT_RISK_PENALTY,
    congestion_penalty: float = DEFAULT_CONGESTION_PENALTY,
) -> Optional[RouteResult]:
    """
    Find the safest path using Dijkstra's algorithm.

    This is slower than A* but guarantees optimality.
    Use as fallback or for validation.

    Args:
        graph:             NetworkX graph from GIS Engine
        source_node:       Starting node ID
        target_node:       Destination node ID
        risk_penalty:      Weight for disaster risk avoidance
        congestion_penalty: Weight for traffic congestion avoidance

    Returns:
        RouteResult or None if no path exists.
    """
    if source_node not in graph or target_node not in graph:
        return None

    cost_fn = make_cost_function(
        risk_penalty=risk_penalty,
        congestion_penalty=congestion_penalty,
    )

    try:
        path_nodes = nx.dijkstra_path(
            graph,
            source=source_node,
            target=target_node,
            weight=cost_fn,
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    return _extract_route_result_dijkstra(graph, path_nodes, cost_fn)
