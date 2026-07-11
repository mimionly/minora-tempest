"""
safe_zone_mapper.py
-------------------
Identifies and classifies safe zones — areas considered low-risk for
sheltering during active disasters.

Safe zones are determined by combining:
- Topographic elevation (above flood levels)
- Distance from wildfire burn perimeters
- Absence of road blockages
- Proximity to mapped shelter nodes
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class SafeZone:
    """Data class representing a single safe zone."""

    __slots__ = (
        "zone_id", "name", "lat", "lon",
        "radius_m", "nearest_node", "safety_score",
        "flood_safe", "fire_safe", "accessible",
    )

    def __init__(
        self,
        zone_id: str,
        name: str,
        lat: float,
        lon: float,
        radius_m: float = 500.0,
        nearest_node: Optional[int] = None,
        safety_score: float = 1.0,
        flood_safe: bool = True,
        fire_safe: bool = True,
        accessible: bool = True,
    ):
        self.zone_id = zone_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.radius_m = radius_m
        self.nearest_node = nearest_node
        self.safety_score = safety_score
        self.flood_safe = flood_safe
        self.fire_safe = fire_safe
        self.accessible = accessible

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


class SafeZoneMapper:
    """
    Builds and maintains a registry of safe zones by integrating
    elevation, disaster simulation outputs, and shelter locations.
    """

    def __init__(
        self,
        node_mapper,
        flood_risk_threshold: float = 0.3,
        fire_risk_threshold: float = 0.3,
    ):
        """
        Args:
            node_mapper: NodeMapper for coordinate-to-node lookup.
            flood_risk_threshold: Max flood risk score for a zone to be 'flood_safe'.
            fire_risk_threshold: Max fire risk score for a zone to be 'fire_safe'.
        """
        self.mapper = node_mapper
        self.flood_threshold = flood_risk_threshold
        self.fire_threshold = fire_risk_threshold
        self._zones: list[SafeZone] = []

    # ------------------------------------------------------------------
    # Zone registration
    # ------------------------------------------------------------------

    def add_zone(
        self,
        zone_id: str,
        name: str,
        lat: float,
        lon: float,
        radius_m: float = 500.0,
    ) -> SafeZone:
        """
        Register a safe zone by geographic position.

        Args:
            zone_id: Unique identifier string.
            name: Human-readable label.
            lat: Zone centroid latitude.
            lon: Zone centroid longitude.
            radius_m: Effective coverage radius in metres.

        Returns:
            The created SafeZone object.
        """
        nearest = self.mapper.nearest_node(lat, lon)
        zone = SafeZone(zone_id, name, lat, lon, radius_m, nearest_node=nearest)
        self._zones.append(zone)
        logger.debug(f"Safe zone '{name}' registered (node={nearest}).")
        return zone

    def add_zones_from_shelters(self, shelter_registry: list[dict]) -> list[SafeZone]:
        """
        Convert mapped shelter records into safe zones.

        Args:
            shelter_registry: Output of ShelterMapper.get_registry().

        Returns:
            List of newly created SafeZone objects.
        """
        created = []
        for i, s in enumerate(shelter_registry):
            lat, lon = s.get("lat"), s.get("lon")
            if lat is None or lon is None:
                continue
            zone = self.add_zone(
                zone_id=f"shelter_{s.get('osm_id', i)}",
                name=s.get("name") or f"Shelter {i + 1}",
                lat=lat,
                lon=lon,
                radius_m=300.0,
            )
            created.append(zone)
        return created

    # ------------------------------------------------------------------
    # Hazard evaluation
    # ------------------------------------------------------------------

    def evaluate_zones(
        self,
        flood_risk_map: Optional[dict] = None,
        fire_risk_map: Optional[dict] = None,
        blocked_nodes: Optional[set] = None,
    ) -> None:
        """
        Re-evaluate safety scores for all zones based on current hazard data.

        Args:
            flood_risk_map: Dict {node_id: flood_risk_score [0,1]}.
            fire_risk_map:  Dict {node_id: fire_risk_score  [0,1]}.
            blocked_nodes:  Set of node IDs with blocked road access.
        """
        flood_risk_map = flood_risk_map or {}
        fire_risk_map = fire_risk_map or {}
        blocked_nodes = blocked_nodes or set()

        for zone in self._zones:
            node = zone.nearest_node
            flood_r = flood_risk_map.get(node, 0.0)
            fire_r = fire_risk_map.get(node, 0.0)

            zone.flood_safe = flood_r < self.flood_threshold
            zone.fire_safe = fire_r < self.fire_threshold
            zone.accessible = node not in blocked_nodes

            # Composite safety score: 1.0 = fully safe, 0.0 = unsafe
            zone.safety_score = round(
                (1.0 - flood_r * 0.5) * (1.0 - fire_r * 0.5)
                * (1.0 if zone.accessible else 0.0),
                4,
            )

        logger.info(f"Evaluated {len(self._zones)} safe zones against hazard data.")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_safe_zones(self) -> list[SafeZone]:
        """Return zones that are flood-safe, fire-safe, and accessible."""
        return [
            z for z in self._zones
            if z.flood_safe and z.fire_safe and z.accessible
        ]

    def get_all_zones(self) -> list[dict]:
        return [z.to_dict() for z in self._zones]

    def get_safe_nodes(self) -> list[int]:
        """Return graph node IDs of currently active safe zones."""
        return [z.nearest_node for z in self.active_safe_zones() if z.nearest_node]
