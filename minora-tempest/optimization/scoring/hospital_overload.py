"""
Hospital Overload — Capacity Monitoring & Routing Penalties
=============================================================

Monitors hospital capacity and adjusts routing decisions:
    - If a hospital is >90% full, routing PENALIZES sending
      more patients there (redirects to less-loaded hospitals)
    - Provides overload alerts for the AI Resource Agent
    - Feeds data to the frontend dashboard

Hospitals are simulated resources with manual capacity input.
"""

from typing import List, Dict, Any, Optional


# Thresholds
LOAD_WARNING = 0.7     # 70% — hospital is getting busy
LOAD_CRITICAL = 0.9    # 90% — stop sending patients here
LOAD_OVERFLOW = 1.0    # 100% — hospital is overwhelmed


def assess_hospital_load(
    hospital_id: str,
    current_patients: int,
    max_capacity: int,
    incoming_patients: int = 0,
) -> Dict[str, Any]:
    """
    Assess the load status of a single hospital.

    Args:
        hospital_id:       Unique hospital identifier
        current_patients:  Current patient count
        max_capacity:      Maximum patient capacity
        incoming_patients: Patients en route (from assigned ambulances)

    Returns:
        Dict with load analysis and recommendations.
    """
    if max_capacity <= 0:
        max_capacity = 1  # prevent division by zero

    effective_patients = current_patients + incoming_patients
    load_ratio = effective_patients / max_capacity
    remaining_capacity = max(0, max_capacity - effective_patients)

    # Determine status
    if load_ratio >= LOAD_OVERFLOW:
        status = "overflow"
        accept_patients = False
        routing_penalty = 100.0  # massive penalty — don't route here
    elif load_ratio >= LOAD_CRITICAL:
        status = "critical"
        accept_patients = False
        routing_penalty = 20.0   # strong penalty — avoid if possible
    elif load_ratio >= LOAD_WARNING:
        status = "warning"
        accept_patients = True
        routing_penalty = 5.0    # mild penalty — prefer other hospitals
    else:
        status = "normal"
        accept_patients = True
        routing_penalty = 0.0

    return {
        "hospital_id": hospital_id,
        "current_patients": current_patients,
        "incoming_patients": incoming_patients,
        "effective_patients": effective_patients,
        "max_capacity": max_capacity,
        "remaining_capacity": remaining_capacity,
        "load_ratio": round(load_ratio, 3),
        "status": status,
        "accept_patients": accept_patients,
        "routing_penalty": routing_penalty,
    }


def batch_assess_hospitals(
    hospitals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Assess all hospitals and sort by available capacity.

    Each hospital dict should have:
        - hospital_id: str
        - current_patients: int
        - max_capacity: int
        - incoming_patients: int (optional)

    Returns:
        List of assessments sorted by load (least loaded first).
    """
    results = []

    for h in hospitals:
        assessment = assess_hospital_load(
            hospital_id=h["hospital_id"],
            current_patients=h.get("current_patients", 0),
            max_capacity=h.get("max_capacity", 50),
            incoming_patients=h.get("incoming_patients", 0),
        )
        results.append(assessment)

    # Sort: hospitals with most remaining capacity first
    results.sort(key=lambda x: x["remaining_capacity"], reverse=True)
    return results


def find_best_hospital(
    hospitals: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Find the hospital with the most remaining capacity
    that is still accepting patients.

    Returns:
        Best hospital assessment dict, or None if all are full.
    """
    assessed = batch_assess_hospitals(hospitals)

    for h in assessed:
        if h["accept_patients"]:
            return h

    return None  # All hospitals are overwhelmed


def get_overload_alerts(
    hospitals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Return hospitals in critical or overflow status.
    These need immediate attention from the AI Resource Agent.
    """
    assessed = batch_assess_hospitals(hospitals)
    return [h for h in assessed if h["status"] in ("critical", "overflow")]
