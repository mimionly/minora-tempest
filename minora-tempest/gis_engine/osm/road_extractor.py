"""
road_extractor.py
-----------------
Extracts road network data from parsed OSM data.
Filters ways by highway tags and builds edge lists for graph construction.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# OSM highway tags considered as driveable roads
ROAD_TAGS = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}

# Tags considered pedestrian / non-motorized paths
PEDESTRIAN_TAGS = {"footway", "cycleway", "path", "steps", "pedestrian", "track"}


class RoadExtractor:
    """
    Filters OSM ways to isolate road segments.
    Produces a list of (node_id_a, node_id_b, metadata) edges.
    """

    def __init__(
        self,
        include_pedestrian: bool = False,
        include_service_roads: bool = True,
    ):
        """
        Args:
            include_pedestrian: Whether to include footways, cycleways, etc.
            include_service_roads: Whether to include service-level roads.
        """
        self.include_pedestrian = include_pedestrian
        self.include_service_roads = include_service_roads

        self._active_tags = set(ROAD_TAGS)
        if not include_service_roads:
            self._active_tags.discard("service")
        if include_pedestrian:
            self._active_tags.update(PEDESTRIAN_TAGS)

    def extract(self, osm_data: dict) -> list[dict]:
        """
        Extract road edges from raw OSM data.

        Args:
            osm_data: Parsed OSM dict with keys 'nodes', 'ways', 'relations'.

        Returns:
            List of edge dicts:
            {
                'from_node': int,
                'to_node': int,
                'way_id': int,
                'highway': str,
                'name': Optional[str],
                'oneway': bool,
                'maxspeed': Optional[int],  # km/h
                'lanes': Optional[int],
            }
        """
        ways = osm_data.get("ways", {})
        edges: list[dict] = []

        for way_id, way in ways.items():
            tags = way.get("tags", {})
            highway = tags.get("highway")

            if highway not in self._active_tags:
                continue

            nodes = way.get("nodes", [])
            oneway = self._parse_oneway(tags.get("oneway", "no"), highway)
            maxspeed = self._parse_maxspeed(tags.get("maxspeed"))
            lanes = self._parse_lanes(tags.get("lanes"))
            name = tags.get("name") or tags.get("ref")

            for i in range(len(nodes) - 1):
                edge = {
                    "from_node": nodes[i],
                    "to_node": nodes[i + 1],
                    "way_id": way_id,
                    "highway": highway,
                    "name": name,
                    "oneway": oneway,
                    "maxspeed": maxspeed,
                    "lanes": lanes,
                }
                edges.append(edge)
                if not oneway:
                    reverse = dict(edge, from_node=nodes[i + 1], to_node=nodes[i])
                    edges.append(reverse)

        logger.info(f"Extracted {len(edges)} road edges from {len(ways)} OSM ways.")
        return edges

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_oneway(value: str, highway: str) -> bool:
        """Return True if this segment is one-directional."""
        if value in ("yes", "true", "1"):
            return True
        if highway in ("motorway", "motorway_link"):
            return True  # motorways are implicitly one-way
        return False

    @staticmethod
    def _parse_maxspeed(value: Optional[str]) -> Optional[int]:
        """Parse maxspeed tag to integer km/h."""
        if value is None:
            return None
        try:
            return int(value.split()[0])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_lanes(value: Optional[str]) -> Optional[int]:
        """Parse lanes tag to integer."""
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None
