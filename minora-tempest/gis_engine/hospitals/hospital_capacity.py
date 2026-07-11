"""
hospital_capacity.py
--------------------
Tracks real-time and surge capacity of hospitals during disasters.

Capacity states:
- NORMAL    — operating within normal parameters
- ELEVATED  — receiving extra patients, some strain
- SURGE     — over-capacity, diverting non-critical cases
- CRITICAL  — effectively non-functional for incoming patients
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CapacityStatus(str, Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    SURGE = "SURGE"
    CRITICAL = "CRITICAL"


def classify_capacity(current_load: float, capacity: float) -> CapacityStatus:
    """
    Classify a hospital's operational status from load vs. capacity.

    Args:
        current_load: Number of patients currently being handled.
        capacity: Total bed / operational capacity.

    Returns:
        CapacityStatus enum value.
    """
    if capacity <= 0:
        return CapacityStatus.CRITICAL
    ratio = current_load / capacity
    if ratio < 0.75:
        return CapacityStatus.NORMAL
    if ratio < 1.0:
        return CapacityStatus.ELEVATED
    if ratio < 1.5:
        return CapacityStatus.SURGE
    return CapacityStatus.CRITICAL


class HospitalCapacityTracker:
    """
    Maintains a live capacity registry for all mapped hospitals.
    Used by routing algorithms to prefer hospitals with available capacity.
    """

    def __init__(self, hospital_registry: list[dict]):
        """
        Args:
            hospital_registry: Output of HospitalMapper.map_hospitals().
        """
        self._hospitals: dict[int, dict] = {}   # keyed by osm_id

        for h in hospital_registry:
            osm_id = h.get("osm_id")
            if osm_id is not None:
                self._hospitals[osm_id] = {
                    **h,
                    "current_load": 0,
                    "capacity": h.get("beds") or 100,  # default 100 if unknown
                    "status": CapacityStatus.NORMAL,
                    "accepting_patients": True,
                }

    # ------------------------------------------------------------------
    # Load updates
    # ------------------------------------------------------------------

    def update_load(self, osm_id: int, load: int) -> CapacityStatus:
        """
        Update the patient load for a hospital and re-classify its status.

        Args:
            osm_id: OSM node/way ID of the hospital.
            load: Current patient count.

        Returns:
            Updated CapacityStatus.
        """
        if osm_id not in self._hospitals:
            logger.warning(f"Hospital {osm_id} not in registry.")
            return CapacityStatus.CRITICAL

        h = self._hospitals[osm_id]
        h["current_load"] = load
        status = classify_capacity(load, h["capacity"])
        h["status"] = status
        h["accepting_patients"] = status != CapacityStatus.CRITICAL

        logger.debug(f"Hospital {osm_id}: load={load}/{h['capacity']} → {status}")
        return status

    def increment_load(self, osm_id: int, delta: int = 1) -> CapacityStatus:
        """Increment a hospital's load by delta patients."""
        if osm_id not in self._hospitals:
            return CapacityStatus.CRITICAL
        current = self._hospitals[osm_id]["current_load"]
        return self.update_load(osm_id, current + delta)

    def mark_offline(self, osm_id: int) -> None:
        """Mark a hospital as completely offline (e.g. flooded building)."""
        if osm_id in self._hospitals:
            self._hospitals[osm_id]["status"] = CapacityStatus.CRITICAL
            self._hospitals[osm_id]["accepting_patients"] = False
            logger.info(f"Hospital {osm_id} marked OFFLINE.")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_status(self, osm_id: int) -> Optional[CapacityStatus]:
        """Return the current status for a hospital."""
        h = self._hospitals.get(osm_id)
        return h["status"] if h else None

    def available_hospitals(self) -> list[dict]:
        """Return hospitals currently accepting patients (not CRITICAL)."""
        return [h for h in self._hospitals.values() if h.get("accepting_patients")]

    def available_nodes(self) -> list[int]:
        """Return graph node IDs of hospitals accepting patients."""
        return [
            h["nearest_node"]
            for h in self.available_hospitals()
            if h.get("nearest_node") is not None
        ]

    def summary(self) -> dict:
        """Return a status summary dict for display/logging."""
        counts: dict[str, int] = {s.value: 0 for s in CapacityStatus}
        for h in self._hospitals.values():
            counts[h["status"].value] += 1
        return {"total": len(self._hospitals), **counts}
