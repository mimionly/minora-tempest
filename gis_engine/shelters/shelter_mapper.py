"""
shelter_mapper.py
-----------------
Identifies and maps emergency shelters from OSM data and external datasets
onto the road graph for evacuation routing.

OSM tags used:
- amenity=shelter
- social_facility=shelter
- emergency=assembly_point
- building=yes + shelter=yes
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# OSM tag combinations that indicate a shelter or assembly point
SHELTER_TAG_PATTERNS = [
    {"amenity": "shelter"},
    {"social_facility": "shelter"},
    {"emergency": "assembly_point"},
    {"amenity": "community_centre"},   # often used as disaster shelters
    {"amenity": "school"},             # secondary: schools as surge shelters
    {"amenity": "townhall"},           # town halls / civic halls
    {"amenity": "place_of_worship"},   # churches, mosques, temples (excellent fallback shelters)
    {"amenity": "sports_centre"},      # stadiums and sports halls
    {"leisure": "sports_centre"},
]


class ShelterMapper:
    """
    Extracts shelter locations from OSM data and snaps them to
    the nearest road graph node for routing.
    """

    def __init__(self, node_mapper, include_schools_as_shelters: bool = True):
        """
        Args:
            node_mapper: NodeMapper instance.
            include_schools_as_shelters: Whether schools count as shelters.
        """
        self.mapper = node_mapper
        self.include_schools = include_schools_as_shelters
        self._registry: list[dict] = []

    def extract_from_osm(self, osm_data: dict) -> list[dict]:
        """
        Extract shelter records from parsed OSM data.

        Args:
            osm_data: Parsed OSM dict with keys 'nodes', 'ways'.

        Returns:
            List of shelter dicts with 'osm_id', 'lat', 'lon', 'name',
            'shelter_type', 'capacity', 'nearest_node', 'distance_to_road_m'.
        """
        raw: list[dict] = []

        for node_id, node in osm_data.get("nodes", {}).items():
            tags = node.get("tags", {})
            shelter_type = self._classify(tags)
            if shelter_type:
                raw.append({
                    "osm_id": node_id,
                    "osm_type": "node",
                    "name": tags.get("name"),
                    "lat": node.get("lat"),
                    "lon": node.get("lon"),
                    "shelter_type": shelter_type,
                    "capacity": self._parse_capacity(tags),
                })

        for way_id, way in osm_data.get("ways", {}).items():
            tags = way.get("tags", {})
            shelter_type = self._classify(tags)
            if shelter_type:
                centroid = self._way_centroid(way, osm_data.get("nodes", {}))
                raw.append({
                    "osm_id": way_id,
                    "osm_type": "way",
                    "name": tags.get("name"),
                    "lat": centroid[0],
                    "lon": centroid[1],
                    "shelter_type": shelter_type,
                    "capacity": self._parse_capacity(tags),
                })

        return self._snap_to_graph(raw)

    def add_external_shelter(
        self, name: str, lat: float, lon: float,
        capacity: Optional[int] = None, shelter_type: str = "designated"
    ) -> dict:
        """
        Manually add a shelter from an external dataset.

        Args:
            name: Shelter name or identifier.
            lat: Latitude.
            lon: Longitude.
            capacity: Maximum occupant count.
            shelter_type: Label for the shelter category.

        Returns:
            Enriched shelter dict with nearest_node.
        """
        record = {
            "osm_id": None, "osm_type": "external",
            "name": name, "lat": lat, "lon": lon,
            "capacity": capacity, "shelter_type": shelter_type,
        }
        snapped = self._snap_to_graph([record])
        if snapped:
            self._registry.append(snapped[0])
            return snapped[0]
        return record

    def get_registry(self) -> list[dict]:
        return self._registry

    def get_routable_nodes(self) -> list[int]:
        return [s["nearest_node"] for s in self._registry if s.get("nearest_node")]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify(self, tags: dict) -> Optional[str]:
        if not self.include_schools and tags.get("amenity") == "school":
            return None
        for pattern in SHELTER_TAG_PATTERNS:
            if all(tags.get(k) == v for k, v in pattern.items()):
                return pattern.get("amenity") or pattern.get("social_facility") or pattern.get("leisure") or "shelter"
        return None

    def _snap_to_graph(self, shelters: list[dict]) -> list[dict]:
        result = []
        for s in shelters:
            lat, lon = s.get("lat"), s.get("lon")
            if lat is None or lon is None:
                continue
            nearest = self.mapper.nearest_node(lat, lon)
            coords = self.mapper.get_node_coords(nearest) if nearest else None
            dist = self._haversine(lat, lon, *coords) if coords else None
            result.append({**s, "nearest_node": nearest, "distance_to_road_m": dist})
        self._registry.extend(result)
        logger.info(f"ShelterMapper: {len(result)} shelters mapped to graph nodes.")
        return result

    @staticmethod
    def _parse_capacity(tags: dict) -> Optional[int]:
        val = tags.get("capacity") or tags.get("shelter_capacity")
        try:
            return int(val) if val else None
        except ValueError:
            return None

    @staticmethod
    def _way_centroid(way: dict, nodes: dict) -> tuple[float, float]:
        ns = [nodes[n] for n in way.get("nodes", []) if n in nodes]
        if not ns:
            return (0.0, 0.0)
        return (
            sum(n["lat"] for n in ns) / len(ns),
            sum(n["lon"] for n in ns) / len(ns),
        )

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
