"""
graph_builder.py
----------------
Builds a weighted directed graph (NetworkX DiGraph) from road edges
produced by road_extractor.py.

The graph nodes represent OSM node IDs (intersections / road endpoints).
The graph edges carry road metadata and computed travel-time weights.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("NetworkX not installed. Graph operations will be unavailable.")


class GraphBuilder:
    """
    Constructs a routable road graph from raw edge data.

    Usage
    -----
    builder = GraphBuilder()
    G = builder.build(edges, nodes)
    """

    def __init__(self, default_speed_kmh: int = 50):
        """
        Args:
            default_speed_kmh: Fallback speed when maxspeed tag is absent.
        """
        if not HAS_NETWORKX:
            raise ImportError("NetworkX is required. Install with: pip install networkx")
        self.default_speed_kmh = default_speed_kmh

    def build(self, edges: list[dict], nodes: dict) -> "nx.DiGraph":
        """
        Build a directed graph from edge and node data.

        Args:
            edges: List of edge dicts from RoadExtractor.extract().
            nodes: OSM nodes dict {node_id: {lat, lon, tags}}.

        Returns:
            NetworkX DiGraph with:
            - Node attributes: lat, lon
            - Edge attributes: way_id, highway, name, oneway,
                               maxspeed, lanes, length_m, travel_time_s
        """
        G = nx.DiGraph()

        # Add nodes with geographic coordinates
        for node_id, node_data in nodes.items():
            G.add_node(
                node_id,
                lat=node_data.get("lat", 0.0),
                lon=node_data.get("lon", 0.0),
            )

        # Add edges with computed weights
        for edge in edges:
            u = edge["from_node"]
            v = edge["to_node"]

            length_m = self._haversine_distance(
                nodes.get(u, {}), nodes.get(v, {})
            )
            speed = edge.get("maxspeed") or self.default_speed_kmh
            travel_time_s = (length_m / 1000.0) / speed * 3600.0

            G.add_edge(
                u, v,
                way_id=edge.get("way_id"),
                highway=edge.get("highway"),
                name=edge.get("name"),
                oneway=edge.get("oneway", False),
                maxspeed=speed,
                lanes=edge.get("lanes"),
                length_m=round(length_m, 2),
                travel_time_s=round(travel_time_s, 4),
            )

        logger.info(
            f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges."
        )
        return G

    def to_undirected(self, G: "nx.DiGraph") -> "nx.Graph":
        """Convert the directed graph to an undirected graph."""
        return G.to_undirected()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_distance(node_a: dict, node_b: dict) -> float:
        """Compute great-circle distance in metres between two OSM nodes."""
        import math
        lat1 = math.radians(node_a.get("lat", 0.0))
        lon1 = math.radians(node_a.get("lon", 0.0))
        lat2 = math.radians(node_b.get("lat", 0.0))
        lon2 = math.radians(node_b.get("lon", 0.0))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 6_371_000 * 2 * math.asin(math.sqrt(a))
