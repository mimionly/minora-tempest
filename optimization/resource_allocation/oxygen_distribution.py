"""
Oxygen Distribution — Medical Supply Routing
==============================================

Allocates oxygen trucks to hospitals/shelters based on:
    1. Hospital overload level (higher load = higher priority)
    2. Distance from nearest oxygen depot
    3. Current oxygen stock at destination

Uses the same greedy nearest-first pattern as ambulance dispatch,
but with a medical-urgency weighting.
"""

from typing import List

import networkx as nx

from optimization.types import (
    Resource,
    Assignment,
    ResourceType,
    ResourceStatus,
    RouteResult,
    NodeId,
    Coord,
)
from optimization.routing.safe_route import find_safe_route, find_nearest_node
from optimization.routing.congestion_aware import apply_route_congestion


def allocate_oxygen(
    graph: nx.Graph,
    oxygen_trucks: List[Resource],
    hospital_nodes: List[dict],
) -> List[Assignment]:
    """
    Allocate oxygen trucks to hospitals based on urgency.

    Args:
        graph:           City graph
        oxygen_trucks:   List of oxygen truck resources
        hospital_nodes:  List of dicts with keys:
                         'hospital_id', 'node_id', 'coords',
                         'load_ratio' (0.0–1.0, higher = more overloaded),
                         'oxygen_stock' (0.0–1.0, lower = more urgent)

    Returns:
        List of Assignments.
    """
    available = [
        t for t in oxygen_trucks
        if t.status == ResourceStatus.AVAILABLE
        and t.resource_type == ResourceType.OXYGEN_TRUCK
    ]

    if not available or not hospital_nodes:
        return []

    # Ensure nodes are resolved
    for res in available:
        if res.current_node is None:
            res.current_node = find_nearest_node(graph, res.current_coords)

    # Score hospitals by urgency
    # urgency = load_ratio × (1 - oxygen_stock)
    # Higher urgency = needs oxygen more desperately
    scored_hospitals = []
    for h in hospital_nodes:
        load = h.get("load_ratio", 0.5)
        stock = h.get("oxygen_stock", 0.5)
        urgency = load * (1.0 - stock)
        scored_hospitals.append((urgency, h))

    # Sort by urgency (highest first)
    scored_hospitals.sort(key=lambda x: x[0], reverse=True)

    assignments: List[Assignment] = []
    used_trucks = set()
    rank = 0

    for urgency, hospital in scored_hospitals:
        if not available:
            break

        h_node = hospital.get("node_id")
        if h_node is None:
            continue

        # Find nearest available truck
        best_truck = None
        best_route = None
        best_cost = float("inf")

        for truck in available:
            if truck.resource_id in used_trucks:
                continue

            route = find_safe_route(graph, truck.current_node, h_node)
            if route is not None and route.total_cost < best_cost:
                best_cost = route.total_cost
                best_route = route
                best_truck = truck

        if best_truck is not None and best_route is not None:
            best_truck.status = ResourceStatus.ASSIGNED
            best_truck.assigned_incident = hospital.get("hospital_id", "unknown")
            used_trucks.add(best_truck.resource_id)

            apply_route_congestion(graph, best_route)

            assignments.append(Assignment(
                resource_id=best_truck.resource_id,
                incident_id=hospital.get("hospital_id", "unknown"),
                route=best_route,
                priority_rank=rank,
            ))
            rank += 1

    return assignments
