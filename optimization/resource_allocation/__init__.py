"""Resource allocation subpackage — ambulance dispatch, supply routing."""

from optimization.resource_allocation.ambulance_dispatch import dispatch_ambulances
from optimization.resource_allocation.vehicle_routing import solve_vehicle_routing
from optimization.resource_allocation.oxygen_distribution import allocate_oxygen
from optimization.resource_allocation.food_distribution import allocate_food

__all__ = [
    "dispatch_ambulances",
    "solve_vehicle_routing",
    "allocate_oxygen",
    "allocate_food",
]
