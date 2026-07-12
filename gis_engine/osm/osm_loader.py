"""
osm_loader.py
-------------
Handles loading and parsing of OpenStreetMap (OSM) data.
Supports loading from .osm, .osm.pbf, and Overpass API responses.
"""

import os
import logging
import json
import urllib.request
import urllib.parse
from typing import Optional, Union

logger = logging.getLogger(__name__)


class OSMLoader:
    """
    Loads raw OSM data from various sources:
    - Local .osm / .osm.pbf files
    - Overpass API queries by bounding box or area name
    """

    def __init__(self, cache_dir: str = "datasets/osm_cache"):
        """
        Args:
            cache_dir: Directory to cache downloaded OSM data.
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def load_from_file(self, filepath: str) -> dict:
        """
        Load OSM data from a local file (.osm or .osm.pbf).

        Args:
            filepath: Absolute or relative path to the OSM file.

        Returns:
            Parsed OSM data as a dictionary with keys:
            'nodes', 'ways', 'relations'.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is unsupported.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"OSM file not found: {filepath}")

        ext = os.path.splitext(filepath)[-1].lower()
        if ext == ".osm":
            return self._parse_xml(filepath)
        elif ext == ".pbf":
            return self._parse_pbf(filepath)
        else:
            raise ValueError(f"Unsupported OSM file format: {ext}")

    def load_from_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        filters: Optional[list] = None,
    ) -> dict:
        """
        Download OSM data for a bounding box via the Overpass API, with local disk caching.
        """
        import urllib.request
        import json
        
        # Create a cache key by rounding coordinates to 3 decimal places (~110m precision grid)
        cache_key = f"{round(min_lat, 3)}_{round(min_lon, 3)}_{round(max_lat, 3)}_{round(max_lon, 3)}"
        cache_filename = os.path.join(self.cache_dir, f"bbox_{cache_key}.json")
        
        if os.path.exists(cache_filename):
            logger.info(f"Loading OSM data from local disk cache for BBOX: {cache_key}...")
            try:
                with open(cache_filename, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    return self._parse_overpass_json(cached_data)
            except Exception as ce:
                logger.warning(f"Failed to read OSM cache file: {ce}. Falling back to network...")

        logger.info(f"Fetching real OSM data for BBOX: {min_lat},{min_lon},{max_lat},{max_lon}...")
        
        # Overpass QL query to get nodes and ways for highways, hospitals, shelters, rescue stations, and waterways
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["amenity"~"hospital|clinic|shelter|community_centre|school|fire_station|police|townhall|place_of_worship|sports_centre"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"~"hospital|clinic|shelter|community_centre|school|fire_station|police|townhall|place_of_worship|sports_centre"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["healthcare"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["healthcare"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["emergency"~"ambulance_station|rescue_station|disaster_response"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["emergency"~"ambulance_station|rescue_station|disaster_response"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["leisure"="sports_centre"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["leisure"="sports_centre"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["waterway"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["natural"="water"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        endpoints = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.openstreetmap.fr/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"
        ]
        
        data = None
        for url in endpoints:
            logger.info(f"Connecting to Overpass API at {url}...")
            req = urllib.request.Request(url, data=query.encode('utf-8'), method='POST')
            req.add_header('User-Agent', 'CivicAutopilot/1.0')
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    logger.info("Successfully fetched data from Overpass API.")
                    
                    # Write fetched data to local cache
                    try:
                        with open(cache_filename, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved OSM data to local disk cache: {cache_filename}")
                    except Exception as we:
                        logger.warning(f"Failed to write to OSM cache file: {we}")
                    break
            except Exception as e:
                logger.warning(f"Failed to fetch from Overpass endpoint {url}: {e}")
                
        if not data:
            logger.error("All Overpass API endpoints failed or timed out.")
            return {"nodes": {}, "ways": {}, "relations": {}}
            
        return self._parse_overpass_json(data)

    def load_from_place(self, place_name: str) -> dict:
        """
        Dynamically geocode a city/place name and fetch its road network.
        
        Args:
            place_name: Location string (e.g., "Sucre, Bolivia" or "Manhattan, New York")
        """
        logger.info(f"Geocoding location: '{place_name}' via Nominatim API...")
        
        # 1. Hit Nominatim API to get the bounding box
        nom_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(place_name)}&format=json&limit=1"
        req = urllib.request.Request(nom_url)
        req.add_header('User-Agent', 'CivicAutopilot/1.0')
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                if not result:
                    raise ValueError(f"Could not find location: {place_name}")
                
                # Nominatim returns bbox as [south, north, west, east] or similar string format:
                # ["-19.0963385", "-18.9863385", "-65.3126002", "-65.2026002"]
                bbox = result[0]['boundingbox']
                south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                
                logger.info(f"Found BBOX for {place_name}: South={south}, North={north}, West={west}, East={east}")
                
                # To prevent overloading the demo with a massive city, we constrain the bbox to a small section
                # roughly 2km x 2km near the center point.
                lat = float(result[0]['lat'])
                lon = float(result[0]['lon'])
                offset = 0.02 # Roughly 2 kilometers
                
                c_south, c_north = lat - offset, lat + offset
                c_west, c_east = lon - offset, lon + offset
                
                logger.info(f"Constraining fetch to a ~2km radius around city center to ensure fast demo execution...")
                return self.load_from_bbox(c_south, c_west, c_north, c_east)
                
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return {"nodes": {}, "ways": {}}

    def _parse_overpass_json(self, data: dict) -> dict:
        """Parse Overpass JSON into the standard dictionary format."""
        nodes = {}
        ways = {}
        
        for element in data.get("elements", []):
            if element["type"] == "node":
                nodes[element["id"]] = {
                    "lat": element["lat"],
                    "lon": element["lon"],
                    "tags": element.get("tags", {})
                }
            elif element["type"] == "way":
                ways[element["id"]] = {
                    "nodes": element.get("nodes", []),
                    "tags": element.get("tags", {})
                }
                
        logger.info(f"Parsed {len(nodes)} nodes and {len(ways)} ways from real data.")
        return {"nodes": nodes, "ways": ways, "relations": {}}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_xml(self, filepath: str) -> dict:
        """Parse a plain .osm XML file and return a structured dict."""
        import xml.etree.ElementTree as ET

        logger.info(f"Parsing OSM XML file: {filepath}")

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            return {"nodes": {}, "ways": {}, "relations": {}}

        nodes = {}
        ways = {}
        relations = {}

        # Parse nodes
        for node in root.findall("node"):
            try:
                node_id = int(node.get("id", 0))
                lat = float(node.get("lat", 0))
                lon = float(node.get("lon", 0))
                tags = {}
                for tag in node.findall("tag"):
                    key = tag.get("k")
                    value = tag.get("v")
                    if key and value:
                        tags[key] = value
                nodes[node_id] = {"lat": lat, "lon": lon, "tags": tags}
            except (ValueError, TypeError):
                continue

        # Parse ways
        for way in root.findall("way"):
            try:
                way_id = int(way.get("id", 0))
                nd_refs = []
                for nd in way.findall("nd"):
                    ref = nd.get("ref")
                    if ref:
                        nd_refs.append(int(ref))
                tags = {}
                for tag in way.findall("tag"):
                    key = tag.get("k")
                    value = tag.get("v")
                    if key and value:
                        tags[key] = value
                ways[way_id] = {"nodes": nd_refs, "tags": tags}
            except (ValueError, TypeError):
                continue

        # Parse relations (basic pass-through)
        for rel in root.findall("relation"):
            try:
                rel_id = int(rel.get("id", 0))
                members = []
                for member in rel.findall("member"):
                    m_type = member.get("type")
                    m_ref = member.get("ref")
                    m_role = member.get("role", "")
                    if m_type and m_ref:
                        members.append({"type": m_type, "ref": int(m_ref), "role": m_role})
                tags = {}
                for tag in rel.findall("tag"):
                    key = tag.get("k")
                    value = tag.get("v")
                    if key and value:
                        tags[key] = value
                relations[rel_id] = {"members": members, "tags": tags}
            except (ValueError, TypeError):
                continue

        logger.info(f"Parsed {len(nodes)} nodes, {len(ways)} ways, {len(relations)} relations from XML.")
        return {"nodes": nodes, "ways": ways, "relations": relations}

    def _parse_pbf(self, filepath: str) -> dict:
        """Parse a binary .osm.pbf file and return a structured dict."""
        try:
            import osmium as osm
        except ImportError:
            logger.error("pyosmium not installed. Install with: pip install pyosmium")
            return {"nodes": {}, "ways": {}, "relations": {}}

        import osmium

        nodes = {}
        ways = {}
        relations = {}

        class OSMHandler(osmium.SimpleHandler):
            def __init__(self):
                super().__init__()
                self.nodes = nodes
                self.ways = ways
                self.relations = relations

            def node(self, n):
                self.nodes[n.id] = {
                    "lat": n.location.lat,
                    "lon": n.location.lon,
                    "tags": dict(n.tags) if n.tags else {}
                }

            def way(self, w):
                ways[w.id] = {
                    "nodes": [node for node in w.nodes],
                    "tags": dict(w.tags) if w.tags else {}
                }

            def relation(self, r):
                members = []
                for m in r.members:
                    members.append({"type": m.type, "ref": m.ref, "role": m.role})
                relations[r.id] = {
                    "members": members,
                    "tags": dict(r.tags) if r.tags else {}
                }

        try:
            handler = OSMHandler()
            handler.apply_file(filepath)
            logger.info(f"Parsed {len(nodes)} nodes and {len(ways)} ways from PBF.")
            return {"nodes": nodes, "ways": ways, "relations": relations}
        except Exception as e:
            logger.error(f"Failed to parse PBF: {e}")
            return {"nodes": {}, "ways": {}, "relations": {}}
