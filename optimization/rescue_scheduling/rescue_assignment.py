"""
Rescue Assignment — Match Rescue Teams to Queued Tasks
=======================================================

Pulls tasks from the RescueQueue and assigns the nearest
available rescue resource (boat, fire truck, ambulance)
based on the incident type and priority.
"""

from typing import List, Optional

import networkx as nx

from optimization.types import (
    Resource,
    Incident,
    Assignment,
    ResourceStatus,
    ResourceType,
    RescueTask,
)
from optimization.rescue_scheduling.rescue_priority import batch_calculate_priorities
from optimization.rescue_scheduling.rescue_queue import RescueQueue
from optimization.routing.safe_route import find_safe_route, find_nearest_node
from optimization.routing.congestion_aware import apply_route_congestion


# Maps incident requirements to acceptable resource types
RESOURCE_COMPATIBILITY = {
    ResourceType.AMBULANCE: [ResourceType.AMBULANCE],
    ResourceType.FIRE_TRUCK: [ResourceType.FIRE_TRUCK],
    ResourceType.RESCUE_BOAT: [ResourceType.RESCUE_BOAT],
    None: [  # No specific requirement — any rescue unit works
        ResourceType.AMBULANCE,
        ResourceType.FIRE_TRUCK,
        ResourceType.RESCUE_BOAT,
        ResourceType.POLICE,
    ],
}


def _find_compatible_resource(
    graph: nx.Graph,
    resources: List[Resource],
    task: RescueTask,
    target_node: int,
    used_ids: set,
) -> Optional[tuple]:
    """Find the nearest compatible and available resource for a task."""
    required_type = None

    # Check if any incident specifies a required type
    # (task doesn't carry this directly, so we accept all by default)
    compatible_types = RESOURCE_COMPATIBILITY.get(required_type, RESOURCE_COMPATIBILITY[None])

    best_resource = None
    best_route = None
    best_cost = float("inf")

    for res in resources:
        if res.resource_id in used_ids:
            continue
        if res.status != ResourceStatus.AVAILABLE:
            continue
        if res.resource_type not in compatible_types:
            continue

        if res.current_node is None:
            res.current_node = find_nearest_node(graph, res.current_coords)

        route = find_safe_route(graph, res.current_node, target_node)
        if route is not None and route.total_cost < best_cost:
            best_cost = route.total_cost
            best_route = route
            best_resource = res

    if best_resource is not None and best_route is not None:
        return best_resource, best_route

    return None


def assign_rescue_teams(
    graph: nx.Graph,
    resources: List[Resource],
    incidents: List[Incident],
    zone_data: dict = None,
    max_assignments: int = 20,
) -> List[Assignment]:
    """
    Full rescue assignment pipeline:
        1. Score all incidents by priority
        2. Build a priority queue
        3. Assign resources in urgency order

    Args:
        graph:            City graph
        resources:        All available rescue resources
        incidents:        Active incidents
        zone_data:        Optional vulnerability/access data per incident
        max_assignments:  Cap on assignments per cycle (prevents overload)

    Returns:
        List of Assignments ordered by priority.
    """
    # Step 1: Calculate priorities
    tasks = batch_calculate_priorities(incidents, zone_data)

    if not tasks:
        return []

    # Step 2: Load into priority queue
    queue = RescueQueue()
    queue.bulk_load(tasks)

    # Step 3: Assign in priority order
    assignments: List[Assignment] = []
    used_resource_ids = set()
    rank = 0

    while not queue.is_empty and rank < max_assignments:
        task = queue.pop()
        if task is None:
            break

        # Find the nearest node for this task's coordinates
        target_node = find_nearest_node(graph, task.coords)
        if target_node is None:
            continue

        result = _find_compatible_resource(
            graph, resources, task, target_node, used_resource_ids,
        )

        if result is None:
            continue  # No resource available for this task

        res, route = result

        # Update resource state
        res.status = ResourceStatus.ASSIGNED
        res.assigned_incident = task.incident_id
        used_resource_ids.add(res.resource_id)

        # Register congestion
        apply_route_congestion(graph, route)

        # Update task with assignment info
        task.assigned_resource = res.resource_id
        task.eta_seconds = route.estimated_time_s

        assignments.append(Assignment(
            resource_id=res.resource_id,
            incident_id=task.incident_id,
            route=route,
            priority_rank=rank,
        ))
        rank += 1

    return assignments
