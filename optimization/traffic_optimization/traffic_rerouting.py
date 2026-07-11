"""
Traffic Rerouting — Civilian Evacuation Flow Management
========================================================

When disaster blocks roads or emergency corridors are activated,
civilian traffic needs to be redirected to alternative routes.

This module computes "civilian-safe" routes that avoid:
    1. Blocked/dangerous roads
    2. Emergency corridors (reserved for rescue)
    3. Already congested roads

The output feeds into the frontend to show civilians
where they SHOULD drive during evacuation.
"""

from typing import List, Optional

import networkx as nx

from optimization.types import RouteResult, NodeId, Coord
from optimization.routing.astar import (
    make_cost_function,
    _make_heuristic,
    _extract_route_result,
    DEFAULT_SPEED_KPH,
)
from optimization.traffic_optimization.emergency_corridors import CORRIDOR_TAG
import math


# Extra penalty weight for civilian routing near corridors
CIVILIAN_CORRIDOR_AVOIDANCE = 10.0


def _civilian_cost_function(u: NodeId, v: NodeId, edge_data: dict) -> float:
    """
    Cost function for civilian routing.

    Same as standard cost function but adds extra penalty for:
        - Emergency corridors (civilians should avoid)
        - High disaster risk areas
    """
    length = edge_data.get("length", 100.0)

    # Blocked roads are impassable
    if edge_data.get("blocked", False):
        return 1_000_000

    # Base risk penalty
    risk = edge_data.get("disaster_risk", 0.0)
    risk = max(0.0, min(1.0, risk))
    risk_cost = 5.0 * length * math.log1p(9.0 * risk)

    # Congestion penalty
    congestion = edge_data.get("congestion", 0.0)
    congestion = max(0.0, min(1.0, congestion))
    congestion_cost = 2.0 * length * congestion

    # Emergency corridor penalty (civilians must avoid)
    corridor_cost = 0.0
    if edge_data.get(CORRIDOR_TAG, False):
        corridor_cost = CIVILIAN_CORRIDOR_AVOIDANCE * length

    # Civilian-specific penalty (if set by edge_penalties module)
    civilian_penalty = edge_data.get("civilian_penalty", 0.0)
    civilian_extra = civilian_penalty * length

    return length + risk_cost + congestion_cost + corridor_cost + civilian_extra


def reroute_civilian_traffic(
    graph: nx.Graph,
    source: NodeId,
    target: NodeId,
) -> Optional[RouteResult]:
    """
    Find the best civilian evacuation route that avoids
    emergency corridors and high-danger zones.

    Args:
        graph:   City graph
        source:  Civilian's current location node
        target:  Shelter or safe zone node

    Returns:
        RouteResult optimized for civilian safety, or None.
    """
    if source not in graph or target not in graph:
        return None

    heuristic = _make_heuristic(target, graph)

    try:
        path_nodes = nx.astar_path(
            graph,
            source=source,
            target=target,
            heuristic=heuristic,
            weight=_civilian_cost_function,
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    result = _extract_route_result(graph, path_nodes, _civilian_cost_function)
    result.algorithm = "astar_civilian"
    return result


def compute_evacuation_routes_for_zone(
    graph: nx.Graph,
    zone_nodes: List[NodeId],
    shelter_nodes: List[NodeId],
    max_routes_per_node: int = 1,
) -> List[RouteResult]:
    """
    Compute civilian evacuation routes for all nodes in a danger zone.

    For each node in the zone, finds the best route to the nearest shelter.

    Args:
        graph:               City graph
        zone_nodes:          Nodes in the danger zone that need evacuation
        shelter_nodes:       Available shelter destination nodes
        max_routes_per_node: Routes to compute per origin (1 = just the best)

    Returns:
        List of RouteResults for all evacuating nodes.
    """
    all_routes: List[RouteResult] = []

    for origin in zone_nodes:
        best_route = None
        best_cost = float("inf")

        for shelter in shelter_nodes:
            route = reroute_civilian_traffic(graph, origin, shelter)
            if route is not None and route.total_cost < best_cost:
                best_cost = route.total_cost
                best_route = route

        if best_route is not None:
            all_routes.append(best_route)

    return all_routes
