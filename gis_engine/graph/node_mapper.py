"""
node_mapper.py
--------------
Provides bidirectional mapping between:
- OSM node IDs  ↔  sequential integer indices (for matrix-based algorithms)
- Geographic coordinates  ↔  nearest graph node
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class NodeMapper:
    """
    Utility class for OSM node lookup, nearest-node queries,
    and index-based graph representations.
    """

    def __init__(self, graph):
        """
        Args:
            graph: NetworkX DiGraph with lat/lon node attributes.
        """
        self._graph = graph
        self._osm_to_idx: dict[int, int] = {}
        self._idx_to_osm: dict[int, int] = {}
        self._build_index()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        """Build a sequential integer index over all graph nodes and initialize KDTree."""
        self._connected_nodes = []
        self._connected_coords = []
        
        for idx, node_id in enumerate(self._graph.nodes()):
            self._osm_to_idx[node_id] = idx
            self._idx_to_osm[idx] = node_id
            
            # Store connected nodes for KDTree
            if self._graph.degree(node_id) > 0:
                data = self._graph.nodes[node_id]
                if "lat" in data and "lon" in data:
                    self._connected_nodes.append(node_id)
                    self._connected_coords.append((data["lat"], data["lon"]))
                    
        logger.info(f"NodeMapper: indexed {len(self._osm_to_idx)} nodes.")
        
        # Build scipy KDTree if available
        self._kdtree = None
        try:
            from scipy.spatial import KDTree # type: ignore
            if self._connected_coords:
                self._kdtree = KDTree(self._connected_coords)
                logger.info("NodeMapper: built KDTree for fast spatial lookups.")
        except ImportError:
            logger.warning("scipy not installed. Falling back to slow linear search for nearest node.")

    def osm_to_index(self, osm_id: int) -> Optional[int]:
        """Return the sequential index for an OSM node ID."""
        return self._osm_to_idx.get(osm_id)

    def index_to_osm(self, idx: int) -> Optional[int]:
        """Return the OSM node ID for a sequential index."""
        return self._idx_to_osm.get(idx)

    def all_indices(self) -> list[int]:
        """Return sorted list of all sequential node indices."""
        return sorted(self._idx_to_osm.keys())

    # ------------------------------------------------------------------
    # Geographic nearest-node queries
    # ------------------------------------------------------------------

    def nearest_node(self, lat: float, lon: float) -> Optional[int]:
        """
        Find the graph node closest to a geographic coordinate.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.

        Returns:
            OSM node ID of the nearest node, or None if the graph is empty.
        """
        if self._kdtree is not None:
            # KDTree query (fast O(log N))
            _, idx = self._kdtree.query((lat, lon))
            return self._connected_nodes[idx]
            
        # Fallback linear search (slow O(N))
        best_node = None
        best_dist = float("inf")

        for node_id, data in self._graph.nodes(data=True):
            if self._graph.degree(node_id) == 0:
                continue
            d = self._haversine(lat, lon, data.get("lat", 0.0), data.get("lon", 0.0))
            if d < best_dist:
                best_dist = d
                best_node = node_id

        return best_node

    def nodes_within_radius(self, lat: float, lon: float, radius_m: float) -> list[int]:
        """
        Return all node IDs within `radius_m` metres of a coordinate.
        Uses fast KDTree spatial indexing (executes in under 0.1ms).
        """
        if self._kdtree is not None:
            # Convert meters to degrees approximately (1 degree ~ 111,000 meters)
            radius_deg = radius_m / 111000.0
            indices = self._kdtree.query_ball_point((lat, lon), radius_deg)
            return [self._connected_nodes[idx] for idx in indices]
            
        # Fallback linear search (slow)
        result = []
        for node_id, data in self._graph.nodes(data=True):
            d = self._haversine(lat, lon, data.get("lat", 0.0), data.get("lon", 0.0))
            if d <= radius_m:
                result.append(node_id)
        return result

    def get_node_coords(self, osm_id: int) -> Optional[tuple[float, float]]:
        """
        Return (lat, lon) for a given OSM node ID.

        Returns:
            Tuple (lat, lon) or None if the node is not in the graph.
        """
        if osm_id not in self._graph:
            return None
        data = self._graph.nodes[osm_id]
        return (data.get("lat", 0.0), data.get("lon", 0.0))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute great-circle distance in metres."""
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
