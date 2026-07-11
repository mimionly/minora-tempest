"""
Safe Route — High-Level Routing Interface
==========================================

This is the PRIMARY function that Person 3 (Backend) will call.

It implements a "Try Best → Fallback" strategy:
1. Try A* (fast, usually optimal)
2. If A* fails, try Dijkstra (guaranteed optimal but slower)
3. If both fail, try with relaxed penalties (graceful degradation)
4. If still no path, return None → "Critical Isolation" alert

This prevents the demo from ever crashing on "No path found."
"""

from typing import Optional, List

import networkx as nx

from optimization.types import RouteResult, NodeId, Coord
from optimization.routing.astar import find_safest_path_astar, _haversine_distance
from optimization.routing.dijkstra import find_safest_path_dijkstra


def find_nearest_node(graph: nx.Graph, coords: Coord) -> Optional[NodeId]:
    """
    Find the graph node closest to the given (lat, lon) coordinates.

    This bridges the gap between manual coordinate inputs
    and the graph's node IDs.
    """
    best_node = None
    best_dist = float("inf")

    for node, data in graph.nodes(data=True):
        node_coord = (data.get("y", 0.0), data.get("x", 0.0))
        dist = _haversine_distance(coords, node_coord)
        if dist < best_dist:
            best_dist = dist
            best_node = node

    return best_node


def find_safe_route(
    graph: nx.Graph,
    source: NodeId,
    target: NodeId,
    risk_penalty: float = 5.0,
    congestion_penalty: float = 2.0,
) -> Optional[RouteResult]:
    """
    Find the safest route with automatic fallback.

    Strategy:
        1. A* with full penalties      → fast + safe
        2. Dijkstra with full penalties → guaranteed optimal
        3. A* with relaxed penalties    → best-effort escape
        4. None                         → critical isolation

    Args:
        graph:             City road graph from Person 1
        source:            Source node ID
        target:            Target node ID
        risk_penalty:      How aggressively to avoid danger
        congestion_penalty: How aggressively to avoid traffic

    Returns:
        RouteResult or None.
    """
    # Strategy 1: A* with full risk avoidance
    result = find_safest_path_astar(
        graph, source, target,
        risk_penalty=risk_penalty,
        congestion_penalty=congestion_penalty,
    )
    if result is not None:
        return result

    # Strategy 2: Dijkstra fallback (slower but more thorough)
    result = find_safest_path_dijkstra(
        graph, source, target,
        risk_penalty=risk_penalty,
        congestion_penalty=congestion_penalty,
    )
    if result is not None:
        result.is_fallback = True
        return result

    # Strategy 3: Relaxed penalties (accept some risk to find ANY path)
    result = find_safest_path_astar(
        graph, source, target,
        risk_penalty=0.5,       # much lower: accept risky roads
        congestion_penalty=0.5,
    )
    if result is not None:
        result.is_fallback = True
        return result

    # Strategy 4: No route exists — area is critically isolated
    return None


def find_safe_route_by_coords(
    graph: nx.Graph,
    source_coords: Coord,
    target_coords: Coord,
    risk_penalty: float = 5.0,
    congestion_penalty: float = 2.0,
) -> Optional[RouteResult]:
    """
    Convenience wrapper: find safe route using (lat, lon) coordinates
    instead of node IDs. Maps coordinates to nearest graph nodes.
    """
    source_node = find_nearest_node(graph, source_coords)
    target_node = find_nearest_node(graph, target_coords)

    if source_node is None or target_node is None:
        return None

    return find_safe_route(
        graph, source_node, target_node,
        risk_penalty=risk_penalty,
        congestion_penalty=congestion_penalty,
    )


def find_multiple_evacuation_routes(
    graph: nx.Graph,
    source: NodeId,
    shelter_nodes: List[NodeId],
    risk_penalty: float = 5.0,
    max_results: int = 3,
) -> List[RouteResult]:
    """
    Find routes to multiple shelters and return the best ones.

    Useful for evacuation: "Find me the 3 safest shelters from here."

    Returns:
        List of RouteResults sorted by total_cost (best first).
    """
    routes = []

    for shelter in shelter_nodes:
        route = find_safe_route(
            graph, source, shelter,
            risk_penalty=risk_penalty,
        )
        if route is not None:
            routes.append(route)

    # Sort by composite cost (safest + shortest first)
    routes.sort(key=lambda r: r.total_cost)

    return routes[:max_results]
