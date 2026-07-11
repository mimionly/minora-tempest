"""
danger_zones.py
---------------
Identifies and maintains geographic danger zones based on active disaster extents.

Danger zones are used to:
- Define mandatory evacuation perimeters
- Filter out unsafe shelters and hospitals
- Generate evacuation direction vectors away from hazard centroids
- Feed into traffic simulation as origin sets
"""

import logging
import math
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ZoneType(str, Enum):
    FLOOD = "FLOOD"
    WILDFIRE = "WILDFIRE"
    COMBINED = "COMBINED"
    CUSTOM = "CUSTOM"


class DangerZone:
    """Represents a circular geographic danger zone."""

    __slots__ = ("zone_id", "zone_type", "centroid_lat", "centroid_lon",
                 "radius_m", "severity", "active")

    def __init__(
        self,
        zone_id: str,
        zone_type: ZoneType,
        centroid_lat: float,
        centroid_lon: float,
        radius_m: float,
        severity: float = 1.0,
    ):
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.centroid_lat = centroid_lat
        self.centroid_lon = centroid_lon
        self.radius_m = radius_m
        self.severity = severity   # 0.0–1.0
        self.active = True

    def contains(self, lat: float, lon: float) -> bool:
        """Return True if the coordinate lies within this zone."""
        return _haversine(self.centroid_lat, self.centroid_lon, lat, lon) <= self.radius_m

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


class DangerZoneManager:
    """
    Manages a collection of active danger zones and classifies
    graph nodes as inside / outside danger.
    """

    def __init__(self, node_mapper):
        """
        Args:
            node_mapper: NodeMapper for coordinate lookups.
        """
        self.mapper = node_mapper
        self._zones: list[DangerZone] = []

    # ------------------------------------------------------------------
    # Zone management
    # ------------------------------------------------------------------

    def add_zone(
        self,
        zone_id: str,
        zone_type: ZoneType,
        centroid_lat: float,
        centroid_lon: float,
        radius_m: float,
        severity: float = 1.0,
    ) -> DangerZone:
        """Register a new danger zone."""
        zone = DangerZone(zone_id, zone_type, centroid_lat, centroid_lon, radius_m, severity)
        self._zones.append(zone)
        logger.info(f"DangerZone '{zone_id}' ({zone_type}) added: r={radius_m:.0f}m.")
        return zone

    def add_from_burn_radius(self, burn_radius_estimator) -> Optional[DangerZone]:
        """
        Create a danger zone from a BurnRadiusEstimator's current state.

        Args:
            burn_radius_estimator: BurnRadiusEstimator instance.

        Returns:
            Created DangerZone, or None if no active fire.
        """
        centroid = burn_radius_estimator.centroid
        if centroid is None:
            return None
        return self.add_zone(
            zone_id="wildfire_zone",
            zone_type=ZoneType.WILDFIRE,
            centroid_lat=centroid[0],
            centroid_lon=centroid[1],
            radius_m=burn_radius_estimator.danger_zone_radius_m,
        )

    def deactivate_zone(self, zone_id: str) -> None:
        """Mark a zone as inactive (hazard resolved)."""
        for z in self._zones:
            if z.zone_id == zone_id:
                z.active = False
                logger.info(f"DangerZone '{zone_id}' deactivated.")

    # ------------------------------------------------------------------
    # Node classification
    # ------------------------------------------------------------------

    def classify_nodes(self, G) -> dict[int, list[str]]:
        """
        Classify every graph node against active danger zones.

        Args:
            G: NetworkX DiGraph.

        Returns:
            {node_id: [zone_id, ...]} — zones the node falls inside.
        """
        classification: dict[int, list[str]] = {}
        active_zones = [z for z in self._zones if z.active]

        for node in G.nodes():
            coords = self.mapper.get_node_coords(node)
            if coords is None:
                continue
            lat, lon = coords
            in_zones = [z.zone_id for z in active_zones if z.contains(lat, lon)]
            if in_zones:
                classification[node] = in_zones

        return classification

    def nodes_in_danger(self, G) -> list[int]:
        """Return all node IDs inside any active danger zone."""
        return list(self.classify_nodes(G).keys())

    def evacuation_direction(
        self, lat: float, lon: float
    ) -> Optional[tuple[float, float]]:
        """
        Compute a recommended evacuation direction vector from a coordinate.

        Returns the direction away from the highest-severity active zone centroid.

        Args:
            lat: Query latitude.
            lon: Query longitude.

        Returns:
            (delta_lat, delta_lon) unit vector pointing away from danger,
            or None if no active zones.
        """
        active = [z for z in self._zones if z.active]
        if not active:
            return None
        worst = max(active, key=lambda z: z.severity)
        dlat = lat - worst.centroid_lat
        dlon = lon - worst.centroid_lon
        mag = math.hypot(dlat, dlon)
        if mag == 0:
            return (0.0, 0.0)
        return (dlat / mag, dlon / mag)

    def get_all_zones(self) -> list[dict]:
        return [z.to_dict() for z in self._zones]
