"""
Food Distribution — Shelter Supply Routing
============================================

Allocates food vans to shelters based on:
    1. Shelter occupancy (higher = more people to feed)
    2. Distance from food depot
    3. Time since last supply delivery

Same pattern as oxygen, different urgency formula.
"""

from typing import List

import networkx as nx

from optimization.types import (
    Resource,
    Assignment,
    ResourceType,
    ResourceStatus,
)
from optimization.routing.safe_route import find_safe_route, find_nearest_node
from optimization.routing.congestion_aware import apply_route_congestion


def allocate_food(
    graph: nx.Graph,
    food_vans: List[Resource],
    shelter_nodes: List[dict],
) -> List[Assignment]:
    """
    Allocate food vans to shelters based on need.

    Args:
        graph:          City graph
        food_vans:      List of food van resources
        shelter_nodes:  List of dicts with keys:
                        'shelter_id', 'node_id', 'coords',
                        'occupancy_ratio' (0.0–1.0),
                        'people_count' (int),
                        'hours_since_supply' (float)

    Returns:
        List of Assignments.
    """
    available = [
        v for v in food_vans
        if v.status == ResourceStatus.AVAILABLE
        and v.resource_type == ResourceType.FOOD_VAN
    ]

    if not available or not shelter_nodes:
        return []

    for res in available:
        if res.current_node is None:
            res.current_node = find_nearest_node(graph, res.current_coords)

    # Score shelters by food urgency
    # urgency = occupancy × people × hours_since_supply
    scored_shelters = []
    for s in shelter_nodes:
        occupancy = s.get("occupancy_ratio", 0.5)
        people = s.get("people_count", 10)
        hours = s.get("hours_since_supply", 1.0)
        urgency = occupancy * people * max(hours, 0.1)
        scored_shelters.append((urgency, s))

    scored_shelters.sort(key=lambda x: x[0], reverse=True)

    assignments: List[Assignment] = []
    used_vans = set()
    rank = 0

    for urgency, shelter in scored_shelters:
        s_node = shelter.get("node_id")
        if s_node is None:
            continue

        best_van = None
        best_route = None
        best_cost = float("inf")

        for van in available:
            if van.resource_id in used_vans:
                continue

            route = find_safe_route(graph, van.current_node, s_node)
            if route is not None and route.total_cost < best_cost:
                best_cost = route.total_cost
                best_route = route
                best_van = van

        if best_van is not None and best_route is not None:
            best_van.status = ResourceStatus.ASSIGNED
            best_van.assigned_incident = shelter.get("shelter_id", "unknown")
            used_vans.add(best_van.resource_id)

            apply_route_congestion(graph, best_route)

            assignments.append(Assignment(
                resource_id=best_van.resource_id,
                incident_id=shelter.get("shelter_id", "unknown"),
                route=best_route,
                priority_rank=rank,
            ))
            rank += 1

    return assignments
