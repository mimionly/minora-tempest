"""
Rescue Priority — Urgency Scoring Engine
==========================================

Calculates a composite urgency score for each incident/zone
to determine rescue order.

Formula:
    urgency = (severity × W1) + (people_affected × W2) +
              (vulnerability × W3) + (access_difficulty × W4)

Where:
    severity         = disaster intensity at location (0.0–1.0)
    people_affected  = number of people in danger
    vulnerability    = elderly/children/medical density (0.0–1.0)
    access_difficulty = how hard it is to reach (0.0–1.0)

Weights are tunable. Higher score = rescue first.
"""

from typing import List, Dict, Any

from optimization.types import Incident, RescueTask, UrgencyLevel


# Tunable weights for the urgency formula
WEIGHT_SEVERITY = 3.0
WEIGHT_PEOPLE = 2.0
WEIGHT_VULNERABILITY = 2.5
WEIGHT_ACCESS_DIFFICULTY = 1.5

# Thresholds for urgency classification
CRITICAL_THRESHOLD = 15.0
HIGH_THRESHOLD = 8.0
MEDIUM_THRESHOLD = 4.0


def calculate_rescue_priority(
    incident: Incident,
    vulnerability_index: float = 0.5,
    access_difficulty: float = 0.3,
) -> RescueTask:
    """
    Calculate the rescue priority score for a single incident.

    Args:
        incident:            The incident to score
        vulnerability_index: Elderly/children density at location (0.0–1.0)
                             (can come from Person 1's population data)
        access_difficulty:   How hard it is to physically reach (0.0–1.0)
                             (derived from blocked roads around the area)

    Returns:
        RescueTask with computed urgency_score and urgency_level.
    """
    # Normalize people_affected to a 0–1 scale (cap at 100 for scoring)
    people_norm = min(incident.people_affected / 100.0, 1.0)

    urgency_score = (
        (incident.severity * WEIGHT_SEVERITY) +
        (people_norm * WEIGHT_PEOPLE) +
        (vulnerability_index * WEIGHT_VULNERABILITY) +
        (access_difficulty * WEIGHT_ACCESS_DIFFICULTY)
    )

    # Classify urgency level
    if urgency_score >= CRITICAL_THRESHOLD:
        level = UrgencyLevel.CRITICAL
    elif urgency_score >= HIGH_THRESHOLD:
        level = UrgencyLevel.HIGH
    elif urgency_score >= MEDIUM_THRESHOLD:
        level = UrgencyLevel.MEDIUM
    else:
        level = UrgencyLevel.LOW

    return RescueTask(
        incident_id=incident.incident_id,
        urgency_score=urgency_score,
        coords=incident.coords,
        people_affected=incident.people_affected,
        urgency_level=level,
    )


def batch_calculate_priorities(
    incidents: List[Incident],
    zone_data: Dict[str, Dict[str, float]] = None,
) -> List[RescueTask]:
    """
    Calculate rescue priority for multiple incidents at once.

    Args:
        incidents:  List of active incidents
        zone_data:  Optional dict mapping incident_id to
                    {'vulnerability': float, 'access_difficulty': float}

    Returns:
        List of RescueTask sorted by urgency (highest first).
    """
    if zone_data is None:
        zone_data = {}

    tasks = []

    for inc in incidents:
        if inc.is_resolved:
            continue

        zd = zone_data.get(inc.incident_id, {})
        vuln = zd.get("vulnerability", 0.5)
        access = zd.get("access_difficulty", 0.3)

        task = calculate_rescue_priority(inc, vuln, access)
        tasks.append(task)

    # Sort by urgency score descending (most urgent first)
    tasks.sort(key=lambda t: t.urgency_score, reverse=True)

    return tasks
