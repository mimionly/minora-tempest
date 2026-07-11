"""Rescue scheduling subpackage — priority scoring and queue management."""

from optimization.rescue_scheduling.rescue_priority import calculate_rescue_priority
from optimization.rescue_scheduling.rescue_queue import RescueQueue
from optimization.rescue_scheduling.rescue_assignment import assign_rescue_teams
from optimization.rescue_scheduling.emergency_priority import classify_emergency

__all__ = [
    "calculate_rescue_priority",
    "RescueQueue",
    "assign_rescue_teams",
    "classify_emergency",
]
