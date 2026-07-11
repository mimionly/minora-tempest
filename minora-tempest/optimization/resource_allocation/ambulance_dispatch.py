"""
Ambulance Dispatch — Nearest-Available Assignment
===================================================

The core logic for matching ambulances to incidents.

Strategy:
    1. Score every (ambulance, incident) pair by travel cost
    2. Assign the cheapest pair first (greedy)
    3. Mark assigned ambulance as unavailable
    4. Repeat until all incidents have an ambulance OR no ambulances remain

This is a greedy heuristic that runs in O(A × I) where A = ambulances,
I = incidents. Fast enough for real-time demo. For optimal multi-vehicle
assignment, use vehicle_routing.py (OR-Tools).
"""

from typing import List, Optional, Tuple

import networkx as nx

from optimization.types import (
    Resource,
    Incident,
    Assignment,
    ResourceStatus,
    ResourceType,
    RouteResult,
)
from optimization.routing.safe_route import find_safe_route, find_nearest_node
from optimization.routing.congestion_aware import apply_route_congestion


def _compute_dispatch_cost(
    graph: nx.Graph,
    resource: Resource,
    incident: Incident,
) -> Tuple[Optional[RouteResult], float]:
    """
    Compute the cost of sending a resource to an incident.
    Returns (route, cost) or (None, inf) if unreachable.
    """
    source = resource.current_node
    target = incident.nearest_node

    if source is None or target is None:
        return None, float("inf")

    route = find_safe_route(graph, source, target)

    if route is None:
        return None, float("inf")

    return route, route.total_cost


def dispatch_ambulances(
    graph: nx.Graph,
    ambulances: List[Resource],
    incidents: List[Incident],
    apply_congestion: bool = True,
) -> List[Assignment]:
    """
    Assign available ambulances to unresolved incidents using
    greedy nearest-first strategy.

    Args:
        graph:             City graph from Person 1
        ambulances:        List of ambulance resources
        incidents:         List of active incidents
        apply_congestion:  Whether to mark assigned routes as congested

    Returns:
        List of Assignments (resource → incident + route).
    """
    # Filter to available ambulances only
    available = [
        a for a in ambulances
        if a.status == ResourceStatus.AVAILABLE
        and a.resource_type == ResourceType.AMBULANCE
    ]

    # Filter to unresolved incidents
    active = [i for i in incidents if not i.is_resolved]

    if not available or not active:
        return []

    # Ensure all resources/incidents have nearest graph nodes
    for res in available:
        if res.current_node is None:
            res.current_node = find_nearest_node(graph, res.current_coords)

    for inc in active:
        if inc.nearest_node is None:
            inc.nearest_node = find_nearest_node(graph, inc.coords)

    # Build cost matrix: (cost, resource_index, incident_index, route)
    candidates: List[Tuple[float, int, int, Optional[RouteResult]]] = []

    for ri, res in enumerate(available):
        for ii, inc in enumerate(active):
            route, cost = _compute_dispatch_cost(graph, res, inc)
            candidates.append((cost, ri, ii, route))

    # Sort by cost (cheapest first)
    candidates.sort(key=lambda x: x[0])

    # Greedy assignment
    assigned_resources = set()
    assigned_incidents = set()
    assignments: List[Assignment] = []
    priority_rank = 0

    for cost, ri, ii, route in candidates:
        if ri in assigned_resources or ii in assigned_incidents:
            continue

        if route is None:
            continue

        res = available[ri]
        inc = active[ii]

        # Mark resource as assigned
        res.status = ResourceStatus.ASSIGNED
        res.assigned_incident = inc.incident_id

        # Apply congestion to route edges
        if apply_congestion:
            apply_route_congestion(graph, route)

        assignments.append(Assignment(
            resource_id=res.resource_id,
            incident_id=inc.incident_id,
            route=route,
            priority_rank=priority_rank,
        ))

        assigned_resources.add(ri)
        assigned_incidents.add(ii)
        priority_rank += 1

    return assignments


def find_nearest_ambulance(
    graph: nx.Graph,
    ambulances: List[Resource],
    incident: Incident,
) -> Optional[Assignment]:
    """
    Find the single nearest available ambulance for one incident.
    Convenience function for single-incident dispatch.
    """
    results = dispatch_ambulances(
        graph,
        ambulances,
        [incident],
        apply_congestion=True,
    )

    return results[0] if results else None
