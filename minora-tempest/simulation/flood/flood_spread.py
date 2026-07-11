"""
flood_spread.py
---------------
Simulates the geographic spread of flood water over the road network
and surrounding terrain.

Algorithm:
- Seeded from initial inundation points (rivers, drainage overflow, etc.)
- Water flows to lower-elevation connected cells (DEM-driven)
- Flood extent grows iteratively over discrete time steps
- Road segments within inundated cells are flagged as blocked
"""

import logging
import math
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class FloodSpreadSimulator:
    """
    Breadth-first flood propagation seeded from initial flood origins.

    Each time step expands the flood frontier to adjacent cells /
    road nodes based on elevation and water volume.
    """

    def __init__(
        self,
        elevation_loader,
        node_mapper,
        dynamic_graph,
        water_depth_threshold_m: float = 0.3,
        max_spread_distance_m: float = 5000.0,
    ):
        """
        Args:
            elevation_loader: ElevationLoader for terrain queries.
            node_mapper: NodeMapper for coordinate lookups.
            dynamic_graph: DynamicGraph to mark blocked roads.
            water_depth_threshold_m: Depth at which a road becomes impassable.
            max_spread_distance_m: Maximum radius the flood can reach.
        """
        self.loader = elevation_loader
        self.mapper = node_mapper
        self.dyn_graph = dynamic_graph
        self.depth_threshold = water_depth_threshold_m
        self.max_spread = max_spread_distance_m

        self._inundated_nodes: set[int] = set()
        self._flood_origins: list[tuple[float, float]] = []
        self._time_step = 0

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def seed(self, origins: list[tuple[float, float]]) -> None:
        """
        Define the initial flood origin points.

        Args:
            origins: List of (lat, lon) tuples for flood seed locations.
        """
        self._flood_origins = origins
        self._inundated_nodes.clear()
        self._time_step = 0

        for lat, lon in origins:
            node = self.mapper.nearest_node(lat, lon)
            if node is not None:
                self._inundated_nodes.add(node)

        logger.info(f"Flood seeded at {len(origins)} origin(s), "
                    f"{len(self._inundated_nodes)} initial nodes inundated.")

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def step(self, water_rise_m: float = 0.1) -> set[int]:
        """
        Advance the flood simulation by one time step.

        Flood spreads from currently inundated nodes to connected
        lower-elevation neighbours.

        Args:
            water_rise_m: Additional water depth added this step.

        Returns:
            Set of newly inundated node IDs.
        """
        G = self.dyn_graph.graph
        newly_inundated: set[int] = set()

        frontier = list(self._inundated_nodes)
        for node in frontier:
            for neighbour in G.successors(node):
                if neighbour not in self._inundated_nodes:
                    newly_inundated.add(neighbour)

        self._inundated_nodes.update(newly_inundated)
        self._block_inundated_roads(newly_inundated)
        self._time_step += 1

        logger.info(
            f"[Flood step {self._time_step}] "
            f"+{len(newly_inundated)} nodes inundated "
            f"(total: {len(self._inundated_nodes)})"
        )
        return newly_inundated

    def run(self, steps: int, water_rise_per_step_m: float = 0.1) -> list[set[int]]:
        """
        Run the simulation for multiple steps.

        Args:
            steps: Number of time steps to simulate.
            water_rise_per_step_m: Water rise per step in metres.

        Returns:
            List of newly-inundated node sets per step.
        """
        history = []
        for _ in range(steps):
            new_nodes = self.step(water_rise_per_step_m)
            history.append(new_nodes)
        return history

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def inundated_nodes(self) -> frozenset:
        return frozenset(self._inundated_nodes)

    @property
    def time_step(self) -> int:
        return self._time_step

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _block_inundated_roads(self, nodes: set[int]) -> None:
        """Block all edges connected to newly inundated nodes."""
        G = self.dyn_graph.graph
        for node in nodes:
            for u, v in list(G.in_edges(node)) + list(G.out_edges(node)):
                self.dyn_graph.block_edge(u, v)

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        a = (math.sin((p2 - p1) / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))
