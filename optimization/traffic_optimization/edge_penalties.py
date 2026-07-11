"""
Edge Penalties — Dynamic Road Weight Management
=================================================

Centralized module for updating edge weights on the city graph.

Person 1 (GIS) sets the initial edge attributes.
Person 2 (Optimization) dynamically adjusts them based on:
    - Disaster spread updates
    - Traffic congestion
    - Emergency corridor activation
    - Route assignments

This module ensures all penalty updates go through
one place — preventing inconsistent edge states.
"""

from typing import List, Dict, Any, Optional

import networkx as nx

from optimization.types import NodeId


def update_edge_penalties(
    graph: nx.Graph,
    edge_updates: List[Dict[str, Any]],
) -> int:
    """
    Batch update edge attributes on the city graph.

    Each update dict should contain:
        - 'u': source node ID
        - 'v': target node ID
        - 'updates': dict of attribute → value

    Example:
        [
            {
                "u": 123,
                "v": 456,
                "updates": {
                    "disaster_risk": 0.85,
                    "congestion": 0.4,
                    "blocked": False
                }
            }
        ]

    Args:
        graph:        City graph
        edge_updates: List of edge update dicts

    Returns:
        Number of edges successfully updated.
    """
    updated_count = 0

    for update in edge_updates:
        u = update.get("u")
        v = update.get("v")
        attrs = update.get("updates", {})

        if u is None or v is None:
            continue

        if not graph.has_edge(u, v):
            continue

        edge_data = graph[u][v]

        # Handle multigraph (OSMnx creates MultiDiGraph)
        if isinstance(edge_data, dict) and 0 in edge_data:
            edge_data = edge_data[0]

        for key, value in attrs.items():
            edge_data[key] = value

        updated_count += 1

    return updated_count


def block_edges(
    graph: nx.Graph,
    edges: List[tuple],
) -> int:
    """
    Mark a list of edges as blocked (impassable).

    Args:
        graph: City graph
        edges: List of (u, v) tuples

    Returns:
        Number of edges blocked.
    """
    updates = [
        {"u": u, "v": v, "updates": {"blocked": True, "disaster_risk": 1.0}}
        for u, v in edges
    ]
    return update_edge_penalties(graph, updates)


def unblock_edges(
    graph: nx.Graph,
    edges: List[tuple],
) -> int:
    """Unblock previously blocked edges."""
    updates = [
        {"u": u, "v": v, "updates": {"blocked": False, "disaster_risk": 0.0}}
        for u, v in edges
    ]
    return update_edge_penalties(graph, updates)


def set_disaster_risk_radius(
    graph: nx.Graph,
    center_node: NodeId,
    radius_hops: int = 3,
    risk_value: float = 0.8,
    decay: float = 0.2,
) -> int:
    """
    Set disaster risk on edges within N hops of a center node,
    with decay (edges further away get lower risk).

    Useful when Person 1 reports "disaster at node X" and
    you need to mark nearby roads as risky.

    Args:
        graph:        City graph
        center_node:  Epicenter of disaster
        radius_hops:  How many hops out to mark
        risk_value:   Risk at the center (0.0–1.0)
        decay:        Risk reduction per hop

    Returns:
        Number of edges updated.
    """
    if center_node not in graph:
        return 0

    updates = []

    # BFS from center
    visited = {center_node: 0}
    queue = [center_node]

    while queue:
        current = queue.pop(0)
        current_depth = visited[current]

        if current_depth >= radius_hops:
            continue

        for neighbor in graph.neighbors(current):
            if neighbor not in visited:
                visited[neighbor] = current_depth + 1
                queue.append(neighbor)

            # Calculate risk with decay
            edge_risk = max(0.0, risk_value - (current_depth * decay))

            updates.append({
                "u": current,
                "v": neighbor,
                "updates": {"disaster_risk": edge_risk},
            })

    return update_edge_penalties(graph, updates)


def reset_penalties(graph: nx.Graph) -> int:
    """
    Reset ALL dynamic penalties on the graph to defaults.
    Use at the start of a new simulation or for cleanup.

    Returns:
        Number of edges reset.
    """
    count = 0

    for u, v, data in graph.edges(data=True):
        edge_data = data
        if isinstance(data, dict) and 0 in data:
            edge_data = data[0]

        edge_data["disaster_risk"] = 0.0
        edge_data["congestion"] = 0.0
        edge_data["blocked"] = False
        edge_data["civilian_penalty"] = 0.0
        edge_data["emergency_corridor"] = False
        count += 1

    return count
