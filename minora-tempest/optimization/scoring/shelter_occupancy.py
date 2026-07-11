"""
Shelter Occupancy — Evacuation Shelter Status Tracker
======================================================

Tracks shelter capacity and helps route evacuees to
shelters that still have room.

Provides:
    - Occupancy status per shelter
    - Recommendation engine for "which shelter to send people to"
    - Overflow detection and alerts
"""

from typing import List, Dict, Any, Optional


# Thresholds
OCCUPANCY_WARNING = 0.7      # 70% — getting full
OCCUPANCY_CRITICAL = 0.9     # 90% — almost full
OCCUPANCY_FULL = 1.0         # 100% — no room


def assess_shelter_status(
    shelter_id: str,
    current_occupants: int,
    max_capacity: int,
    has_medical: bool = False,
    has_food: bool = True,
    has_water: bool = True,
) -> Dict[str, Any]:
    """
    Assess the status of a single shelter.

    Args:
        shelter_id:         Unique shelter identifier
        current_occupants:  Current people in shelter
        max_capacity:       Maximum capacity
        has_medical:        Whether medical staff is present
        has_food:           Whether food supplies are available
        has_water:          Whether water is available

    Returns:
        Dict with shelter analysis.
    """
    if max_capacity <= 0:
        max_capacity = 1

    occupancy_ratio = current_occupants / max_capacity
    remaining = max(0, max_capacity - current_occupants)

    # Determine status
    if occupancy_ratio >= OCCUPANCY_FULL:
        status = "full"
        accept_evacuees = False
    elif occupancy_ratio >= OCCUPANCY_CRITICAL:
        status = "critical"
        accept_evacuees = True
    elif occupancy_ratio >= OCCUPANCY_WARNING:
        status = "warning"
        accept_evacuees = True
    else:
        status = "available"
        accept_evacuees = True

    # Supply score (0–1, higher = better supplied)
    supply_score = (
        (0.4 if has_food else 0.0) +
        (0.3 if has_water else 0.0) +
        (0.3 if has_medical else 0.0)
    )

    # Overall desirability (for routing: prefer shelters that are
    # less full AND better supplied)
    desirability = (1.0 - occupancy_ratio) * 0.6 + supply_score * 0.4

    return {
        "shelter_id": shelter_id,
        "current_occupants": current_occupants,
        "max_capacity": max_capacity,
        "remaining_capacity": remaining,
        "occupancy_ratio": round(occupancy_ratio, 3),
        "status": status,
        "accept_evacuees": accept_evacuees,
        "has_medical": has_medical,
        "has_food": has_food,
        "has_water": has_water,
        "supply_score": round(supply_score, 2),
        "desirability": round(desirability, 4),
    }


def batch_assess_shelters(
    shelters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Assess all shelters and sort by desirability.

    Each shelter dict should have:
        - shelter_id: str
        - current_occupants: int
        - max_capacity: int
        - has_medical: bool (optional)
        - has_food: bool (optional)
        - has_water: bool (optional)

    Returns:
        List sorted by desirability (best first).
    """
    results = []

    for s in shelters:
        assessment = assess_shelter_status(
            shelter_id=s["shelter_id"],
            current_occupants=s.get("current_occupants", 0),
            max_capacity=s.get("max_capacity", 100),
            has_medical=s.get("has_medical", False),
            has_food=s.get("has_food", True),
            has_water=s.get("has_water", True),
        )
        results.append(assessment)

    results.sort(key=lambda x: x["desirability"], reverse=True)
    return results


def find_best_shelter(
    shelters: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Find the most desirable shelter that is still accepting evacuees.

    Returns:
        Best shelter dict, or None if all are full.
    """
    assessed = batch_assess_shelters(shelters)

    for s in assessed:
        if s["accept_evacuees"]:
            return s

    return None


def get_shelter_overflow_alerts(
    shelters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return shelters that are full or critically full."""
    assessed = batch_assess_shelters(shelters)
    return [s for s in assessed if s["status"] in ("critical", "full")]


def get_shelter_summary(shelters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get an aggregate summary of all shelters.
    Used by the frontend dashboard.
    """
    assessed = batch_assess_shelters(shelters)

    total_capacity = sum(s["max_capacity"] for s in assessed)
    total_occupants = sum(s["current_occupants"] for s in assessed)
    total_remaining = sum(s["remaining_capacity"] for s in assessed)
    accepting = sum(1 for s in assessed if s["accept_evacuees"])

    return {
        "total_shelters": len(assessed),
        "accepting_shelters": accepting,
        "full_shelters": len(assessed) - accepting,
        "total_capacity": total_capacity,
        "total_occupants": total_occupants,
        "total_remaining": total_remaining,
        "overall_occupancy": round(total_occupants / max(total_capacity, 1), 3),
        "shelters": assessed,
    }
