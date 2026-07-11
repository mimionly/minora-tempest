"""
Rerouting Engine — Dynamic Path Adaptation
============================================

Determines WHEN a resource should be rerouted and computes
the new path. Uses Hysteresis to prevent route oscillation
(flip-flopping between two routes every update cycle).

Key Principle:
    A reroute is only triggered if the NEW path is significantly
    better than the CURRENT path. "Significantly" is controlled
    by REROUTE_THRESHOLD (default: 20% improvement required).
"""

from typing import Optional

import networkx as nx

from optimization.types import RouteResult, NodeId
from optimization.routing.safe_route import find_safe_route
from optimization.routing.congestion_aware import (
    clear_route_congestion,
    apply_route_congestion,
)
from optimization.routing.astar import make_cost_function


# Minimum improvement ratio to trigger reroute (prevents oscillation)
REROUTE_THRESHOLD = 0.20  # 20% — new route must be 20% cheaper

# Maximum risk on any single edge before forced reroute
CRITICAL_RISK_THRESHOLD = 0.85


def _compute_current_path_cost(
    graph: nx.Graph,
    path_nodes: list,
) -> float:
    """Recompute the cost of an existing path with current edge weights."""
    cost_fn = make_cost_function()
    total = 0.0

    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]

        if not graph.has_edge(u, v):
            return float("inf")  # edge was removed/blocked

        edge_data = graph[u][v]
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        total += cost_fn(u, v, edge_data)

    return total


def _path_has_critical_risk(graph: nx.Graph, path_nodes: list) -> bool:
    """Check if any edge on the current path has dangerously high risk."""
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]

        if not graph.has_edge(u, v):
            return True  # edge gone = critical

        edge_data = graph[u][v]
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        if edge_data.get("blocked", False):
            return True

        if edge_data.get("disaster_risk", 0.0) >= CRITICAL_RISK_THRESHOLD:
            return True

    return False


def should_reroute(
    graph: nx.Graph,
    current_route: RouteResult,
    current_position_index: int = 0,
) -> bool:
    """
    Decide if a resource should be rerouted.

    Triggers reroute if:
        1. Any edge on remaining path is blocked or critically risky
        2. A significantly better alternative exists (>20% improvement)

    Args:
        graph:                  Current city graph state
        current_route:          The resource's current assigned route
        current_position_index: How far along the path the resource has traveled

    Returns:
        True if rerouting is recommended.
    """
    remaining_nodes = current_route.path_nodes[current_position_index:]

    if len(remaining_nodes) < 2:
        return False  # already at destination

    # Check 1: Critical danger on current path
    if _path_has_critical_risk(graph, remaining_nodes):
        return True

    # Check 2: Is there a significantly better alternative?
    current_cost = _compute_current_path_cost(graph, remaining_nodes)
    if current_cost == float("inf"):
        return True  # path is broken

    source = remaining_nodes[0]
    target = remaining_nodes[-1]

    alternative = find_safe_route(graph, source, target)
    if alternative is None:
        return False  # no alternative available, keep current

    improvement = (current_cost - alternative.total_cost) / max(current_cost, 1.0)

    return improvement >= REROUTE_THRESHOLD


def compute_reroute(
    graph: nx.Graph,
    current_route: RouteResult,
    current_position_index: int = 0,
) -> Optional[RouteResult]:
    """
    Compute a new route from the resource's current position
    to the original destination.

    Also handles congestion cleanup: removes congestion from
    the old remaining path and adds it to the new one.

    Args:
        graph:                  Current city graph
        current_route:          Existing route
        current_position_index: Current position along the path

    Returns:
        New RouteResult, or None if no better route exists.
    """
    remaining_nodes = current_route.path_nodes[current_position_index:]

    if len(remaining_nodes) < 2:
        return None

    source = remaining_nodes[0]
    target = current_route.path_nodes[-1]  # original destination

    # Clear congestion from old remaining path
    old_remaining = RouteResult(
        path_nodes=remaining_nodes,
        path_coords=[],
        total_distance_m=0,
        total_cost=0,
        estimated_time_s=0,
        risk_score=0,
        algorithm="",
    )
    clear_route_congestion(graph, old_remaining)

    # Find new route
    new_route = find_safe_route(graph, source, target)

    if new_route is not None:
        apply_route_congestion(graph, new_route)

    return new_route
