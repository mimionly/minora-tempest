"""
hospital_extractor.py
---------------------
Extracts hospital / medical facility nodes and polygons from OSM data.
Uses amenity=hospital, amenity=clinic, healthcare=* tags.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# OSM tags that identify medical facilities
HOSPITAL_AMENITY_VALUES = {"hospital", "clinic", "doctors", "health_post"}
HEALTHCARE_VALUES = {"hospital", "clinic", "centre", "doctor", "pharmacy"}


class HospitalExtractor:
    """
    Scans OSM nodes and ways for healthcare facilities.
    Returns structured records suitable for hospital_mapper.py.
    """

    def __init__(self, include_clinics: bool = True, include_pharmacies: bool = False):
        """
        Args:
            include_clinics: Include smaller clinics and health posts.
            include_pharmacies: Include pharmacies.
        """
        self.include_clinics = include_clinics
        self.include_pharmacies = include_pharmacies

    def extract(self, osm_data: dict) -> list[dict]:
        """
        Extract healthcare facility records from raw OSM data.

        Args:
            osm_data: Parsed OSM dict with keys 'nodes', 'ways', 'relations'.

        Returns:
            List of facility dicts:
            {
                'osm_id': int,
                'osm_type': 'node' | 'way',
                'name': Optional[str],
                'lat': Optional[float],
                'lon': Optional[float],
                'amenity': Optional[str],
                'healthcare': Optional[str],
                'beds': Optional[int],
                'emergency': bool,
                'operator': Optional[str],
                'addr_full': Optional[str],
            }
        """
        facilities: list[dict] = []

        # --- Scan nodes ---
        for node_id, node in osm_data.get("nodes", {}).items():
            tags = node.get("tags", {})
            if self._is_healthcare(tags):
                facilities.append(self._build_record(node_id, "node", node, tags))

        # --- Scan ways (polygon footprints of large hospitals) ---
        for way_id, way in osm_data.get("ways", {}).items():
            tags = way.get("tags", {})
            if self._is_healthcare(tags):
                centroid = self._way_centroid(way, osm_data.get("nodes", {}))
                facilities.append(
                    self._build_record(way_id, "way", centroid, tags)
                )

        logger.info(f"Extracted {len(facilities)} healthcare facilities from OSM data.")
        return facilities

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_healthcare(self, tags: dict) -> bool:
        """Return True if the tag set represents a healthcare facility."""
        amenity = tags.get("amenity", "")
        healthcare = tags.get("healthcare", "")

        if amenity == "hospital":
            return True
        if healthcare in HEALTHCARE_VALUES:
            if healthcare == "pharmacy" and not self.include_pharmacies:
                return False
            return True
        if self.include_clinics and amenity in HOSPITAL_AMENITY_VALUES:
            return True
        return False

    @staticmethod
    def _build_record(
        osm_id: int,
        osm_type: str,
        node: dict,
        tags: dict,
    ) -> dict:
        beds_raw = tags.get("beds") or tags.get("capacity:beds")
        try:
            beds = int(beds_raw) if beds_raw else None
        except ValueError:
            beds = None

        return {
            "osm_id": osm_id,
            "osm_type": osm_type,
            "name": tags.get("name"),
            "lat": node.get("lat"),
            "lon": node.get("lon"),
            "amenity": tags.get("amenity"),
            "healthcare": tags.get("healthcare"),
            "beds": beds,
            "emergency": tags.get("emergency", "no").lower() == "yes",
            "operator": tags.get("operator"),
            "addr_full": tags.get("addr:full") or tags.get("addr:street"),
        }

    @staticmethod
    def _way_centroid(way: dict, nodes: dict) -> dict:
        """Compute approximate centroid of a way polygon."""
        way_nodes = [nodes[n] for n in way.get("nodes", []) if n in nodes]
        if not way_nodes:
            return {"lat": None, "lon": None}
        avg_lat = sum(n["lat"] for n in way_nodes if n.get("lat")) / max(len(way_nodes), 1)
        avg_lon = sum(n["lon"] for n in way_nodes if n.get("lon")) / max(len(way_nodes), 1)
        return {"lat": avg_lat, "lon": avg_lon}
