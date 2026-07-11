"""
hospital_mapper.py
------------------
Maps extracted hospital records (from osm/hospital_extractor.py) onto
the road graph by snapping each facility to its nearest graph node.

Produces a structured registry of hospitals with routing anchor points.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HospitalMapper:
    """
    Registers hospitals as accessible destinations on the road graph.

    Each hospital is assigned:
    - nearest_node: graph node used as routing target
    - distance_to_road_m: distance from facility to that node
    """

    def __init__(self, node_mapper):
        """
        Args:
            node_mapper: NodeMapper instance from gis-engine/graph/node_mapper.py.
        """
        self.mapper = node_mapper
        self._registry: list[dict] = []

    def map_hospitals(self, hospitals: list[dict]) -> list[dict]:
        """
        Snap each hospital record to the nearest graph node.

        Args:
            hospitals: List of hospital dicts from HospitalExtractor.extract().

        Returns:
            Enriched list of hospital dicts with added fields:
            - nearest_node: int OSM node ID
            - distance_to_road_m: float
        """
        self._registry = []
        skipped = 0

        for h in hospitals:
            lat = h.get("lat")
            lon = h.get("lon")

            if lat is None or lon is None:
                logger.debug(f"Skipping hospital {h.get('osm_id')} — no coordinates.")
                skipped += 1
                continue

            nearest = self.mapper.nearest_node(lat, lon)
            if nearest is None:
                skipped += 1
                continue

            road_coords = self.mapper.get_node_coords(nearest)
            dist = self._haversine(lat, lon, *road_coords) if road_coords else None

            enriched = {**h, "nearest_node": nearest, "distance_to_road_m": dist}
            self._registry.append(enriched)

        logger.info(
            f"HospitalMapper: mapped {len(self._registry)} hospitals "
            f"({skipped} skipped, no coordinates)."
        )
        return self._registry

    def get_registry(self) -> list[dict]:
        """Return the current hospital registry."""
        return self._registry

    def get_routable_nodes(self) -> list[int]:
        """Return list of graph node IDs that anchor hospitals."""
        return [h["nearest_node"] for h in self._registry if h.get("nearest_node") is not None]

    def get_emergency_nodes(self) -> list[int]:
        """Return node IDs for hospitals that have emergency departments."""
        return [
            h["nearest_node"]
            for h in self._registry
            if h.get("emergency") and h.get("nearest_node") is not None
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
