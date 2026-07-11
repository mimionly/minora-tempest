"""
Emergency Priority — Incident Classification Engine
=====================================================

Classifies incoming incidents into urgency tiers and
determines the appropriate response level.

This is the "triage nurse" of the system — it decides
what kind of response each incident needs BEFORE the
rescue queue processes it.
"""

from typing import Dict, Any

from optimization.types import Incident, UrgencyLevel, ResourceType


# Classification rules based on incident properties
SEVERITY_THRESHOLDS = {
    UrgencyLevel.CRITICAL: 0.8,
    UrgencyLevel.HIGH: 0.6,
    UrgencyLevel.MEDIUM: 0.3,
    UrgencyLevel.LOW: 0.0,
}

PEOPLE_THRESHOLDS = {
    UrgencyLevel.CRITICAL: 50,
    UrgencyLevel.HIGH: 20,
    UrgencyLevel.MEDIUM: 5,
    UrgencyLevel.LOW: 0,
}


def classify_emergency(incident: Incident) -> Dict[str, Any]:
    """
    Classify an incident and determine response requirements.

    Returns a dict with:
        - urgency_level: UrgencyLevel
        - recommended_resources: list of ResourceType
        - recommended_count: number of units needed
        - escalation_needed: bool (should alert command center)
        - rationale: human-readable explanation (for Explanation Agent)
    """
    severity = incident.severity
    people = incident.people_affected
    rationale_parts = []

    # Determine urgency from severity
    urgency_from_severity = UrgencyLevel.LOW
    for level, threshold in SEVERITY_THRESHOLDS.items():
        if severity >= threshold:
            urgency_from_severity = level
            break

    # Determine urgency from people affected
    urgency_from_people = UrgencyLevel.LOW
    for level, threshold in PEOPLE_THRESHOLDS.items():
        if people >= threshold:
            urgency_from_people = level
            break

    # Take the higher of the two
    urgency_order = [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH, UrgencyLevel.MEDIUM, UrgencyLevel.LOW]

    idx_sev = urgency_order.index(urgency_from_severity)
    idx_ppl = urgency_order.index(urgency_from_people)
    final_urgency = urgency_order[min(idx_sev, idx_ppl)]

    # Determine recommended resources
    recommended_resources = []
    recommended_count = 1

    if incident.requires_type:
        recommended_resources.append(incident.requires_type)
    else:
        recommended_resources.append(ResourceType.AMBULANCE)

    if final_urgency == UrgencyLevel.CRITICAL:
        recommended_count = 3
        recommended_resources = [
            ResourceType.AMBULANCE,
            ResourceType.FIRE_TRUCK,
            ResourceType.POLICE,
        ]
        rationale_parts.append(
            f"CRITICAL: Severity {severity:.1f} with {people} people affected"
        )
    elif final_urgency == UrgencyLevel.HIGH:
        recommended_count = 2
        recommended_resources.append(ResourceType.POLICE)
        rationale_parts.append(
            f"HIGH priority: Severity {severity:.1f}, {people} people at risk"
        )
    elif final_urgency == UrgencyLevel.MEDIUM:
        rationale_parts.append(
            f"MEDIUM priority: Severity {severity:.1f}, {people} people affected"
        )
    else:
        rationale_parts.append(
            f"LOW priority: Severity {severity:.1f}, {people} people — monitor only"
        )

    # Escalation check
    escalation_needed = (
        final_urgency == UrgencyLevel.CRITICAL or people >= 100
    )

    if escalation_needed:
        rationale_parts.append("ESCALATION: Command center notification required")

    # Update the incident's urgency
    incident.urgency = final_urgency

    return {
        "incident_id": incident.incident_id,
        "urgency_level": final_urgency.value,
        "recommended_resources": [r.value for r in recommended_resources],
        "recommended_count": recommended_count,
        "escalation_needed": escalation_needed,
        "rationale": ". ".join(rationale_parts),
    }


def batch_classify(incidents: list) -> list:
    """Classify multiple incidents at once."""
    return [classify_emergency(inc) for inc in incidents if not inc.is_resolved]
