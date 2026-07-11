"""
A* Routing Algorithm — Risk-Aware Pathfinding
==============================================

Uses NetworkX's A* implementation with a custom cost function
that balances distance, disaster risk, and traffic congestion.

The heuristic uses Haversine distance for GIS coordinates,
ensuring admissibility (never overestimates true travel cost).

Person 1 provides the graph with edge attributes:
    - 'length'         : road distance in meters
    - 'disaster_risk'  : 0.0–1.0 (set by Disaster Simulation)
    - 'congestion'     : 0.0–1.0 (set by Traffic Optimization)
    - 'blocked'        : bool (True = road impassable)
    - 'speed_kph'      : speed limit or effective speed

Person 2 reads those attributes and computes optimal paths.
"""

import math
from typing import Optional, Callable

import networkx as nx

from optimization.types import RouteResult, NodeId, Coord


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS_M = 6_371_000  # meters

# Cost function weights — tunable during demo
DEFAULT_RISK_PENALTY = 5.0
DEFAULT_CONGESTION_PENALTY = 2.0
DEFAULT_BLOCKED_PENALTY = 1_000_000  # effectively infinite

# Fallback speed when edge has no speed attribute
DEFAULT_SPEED_KPH = 30.0


# ---------------------------------------------------------------------------
# Haversine Heuristic (admissible for GIS coordinates)
# ---------------------------------------------------------------------------
def _haversine_distance(coord1: Coord, coord2: Coord) -> float:
    """
    Calculate the great-circle distance between two points
    on Earth using the Haversine formula.

    Args:
        coord1: (latitude, longitude) in degrees
        coord2: (latitude, longitude) in degrees

    Returns:
        Distance in meters.
    """
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_M * c


def _make_heuristic(target_node: NodeId, graph: nx.Graph):
    """
    Create a heuristic function for A* that estimates distance
    from any node to the target using Haversine.
    """
    target_data = graph.nodes[target_node]
    target_coord = (target_data.get("y", 0.0), target_data.get("x", 0.0))

    def heuristic(node: NodeId, _target: NodeId) -> float:
        node_data = graph.nodes[node]
        node_coord = (node_data.get("y", 0.0), node_data.get("x", 0.0))
        return _haversine_distance(node_coord, target_coord)

    return heuristic


# ---------------------------------------------------------------------------
# Dynamic Cost Function
# ---------------------------------------------------------------------------
def make_cost_function(
    risk_penalty: float = DEFAULT_RISK_PENALTY,
    congestion_penalty: float = DEFAULT_CONGESTION_PENALTY,
    blocked_penalty: float = DEFAULT_BLOCKED_PENALTY,
) -> Callable:
    """
    Create a dynamic edge-cost function for A*.

    Total cost = length + (λ × risk) + (μ × congestion) + blocked_penalty

    This uses logarithmic scaling on risk to aggressively avoid
    high-danger zones while not overreacting to low-risk areas.
    """

    def cost_function(u: NodeId, v: NodeId, edge_data: dict) -> float:
        # Base: physical road distance
        length = edge_data.get("length", 100.0)

        # If road is blocked, make it effectively impassable
        if edge_data.get("blocked", False):
            return blocked_penalty

        # Risk penalty: logarithmic scaling (0.0 → 0, 0.5 → moderate, 0.9 → huge)
        risk = edge_data.get("disaster_risk", 0.0)
        risk = max(0.0, min(1.0, risk))  # clamp
        # log(1 + 9*risk) maps [0,1] → [0, 1.0] on a log scale
        risk_cost = risk_penalty * length * math.log1p(9.0 * risk)

        # Congestion penalty: linear scaling
        congestion = edge_data.get("congestion", 0.0)
        congestion = max(0.0, min(1.0, congestion))
        congestion_cost = congestion_penalty * length * congestion

        return length + risk_cost + congestion_cost

    return cost_function


# ---------------------------------------------------------------------------
# Path Metadata Extraction
# ---------------------------------------------------------------------------
def _extract_route_result(
    graph: nx.Graph,
    path_nodes: list,
    cost_fn: Callable,
) -> RouteResult:
    """
    Given a list of nodes forming a path, extract full route metadata.
    """
    path_coords = []
    total_distance = 0.0
    total_cost = 0.0
    total_risk = 0.0
    total_time = 0.0

    for node in path_nodes:
        data = graph.nodes[node]
        lat = data.get("y", 0.0)
        lon = data.get("x", 0.0)
        path_coords.append((lat, lon))

    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        edge_data = graph[u][v]

        # Handle multigraph: take the first edge (key=0)
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        length = edge_data.get("length", 100.0)
        total_distance += length

        cost = cost_fn(u, v, edge_data)
        total_cost += cost

        risk = edge_data.get("disaster_risk", 0.0)
        total_risk += risk

        speed_kph = edge_data.get("speed_kph", DEFAULT_SPEED_KPH)
        if speed_kph <= 0:
            speed_kph = DEFAULT_SPEED_KPH
        total_time += (length / 1000.0) / speed_kph * 3600  # seconds

    num_edges = max(len(path_nodes) - 1, 1)
    avg_risk = total_risk / num_edges

    return RouteResult(
        path_nodes=path_nodes,
        path_coords=path_coords,
        total_distance_m=total_distance,
        total_cost=total_cost,
        estimated_time_s=total_time,
        risk_score=avg_risk,
        algorithm="astar",
        is_fallback=False,
    )


# ---------------------------------------------------------------------------
# Main A* Function
# ---------------------------------------------------------------------------
def find_safest_path_astar(
    graph: nx.Graph,
    source_node: NodeId,
    target_node: NodeId,
    risk_penalty: float = DEFAULT_RISK_PENALTY,
    congestion_penalty: float = DEFAULT_CONGESTION_PENALTY,
) -> Optional[RouteResult]:
    """
    Find the safest path between two nodes using A* with
    risk-aware dynamic cost function.

    Args:
        graph:             NetworkX graph from GIS Engine (Person 1)
        source_node:       Starting node ID
        target_node:       Destination node ID
        risk_penalty:      Weight for disaster risk avoidance (higher = more avoidant)
        congestion_penalty: Weight for traffic congestion avoidance

    Returns:
        RouteResult with full path metadata, or None if no path exists.

    Graceful Degradation:
        If no path exists (all routes blocked), returns None.
        Person 3's backend should handle this as "Critical Isolation."
    """
    if source_node not in graph or target_node not in graph:
        return None

    cost_fn = make_cost_function(
        risk_penalty=risk_penalty,
        congestion_penalty=congestion_penalty,
    )

    heuristic = _make_heuristic(target_node, graph)

    try:
        path_nodes = nx.astar_path(
            graph,
            source=source_node,
            target=target_node,
            heuristic=heuristic,
            weight=cost_fn,
        )
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None

    return _extract_route_result(graph, path_nodes, cost_fn)
