"""
traffic_simulation.py
---------------------
Simulates vehicle flow on the road network during disaster evacuations.

Models:
- Origin-destination (OD) demand generation from population / hazard zones
- Route assignment (shortest-path based, with stochastic rerouting)
- Volume-to-capacity ratio computation per edge
- Integration with congestion_model.py for dynamic weight updates
"""

import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False


class TrafficSimulator:
    """
    Simulates evacuation traffic flow on a road network.

    Steps:
    1. Seed demand from evacuation zones (origins) to safe zones (destinations).
    2. Route vehicles using shortest paths.
    3. Accumulate volume per edge.
    4. Output volume_capacity_ratio per edge for congestion computation.
    """

    def __init__(
        self,
        dynamic_graph,
        node_mapper,
        default_lane_capacity_vph: int = 1200,
    ):
        """
        Args:
            dynamic_graph: DynamicGraph instance.
            node_mapper: NodeMapper instance.
            default_lane_capacity_vph: Default vehicles/hour/lane if unspecified.
        """
        if not HAS_NX:
            raise ImportError("NetworkX required: pip install networkx")
        self.dyn_graph = dynamic_graph
        self.mapper = node_mapper
        self.default_capacity = default_lane_capacity_vph

        self._volume: dict[tuple, float] = {}   # (u, v) → vehicles/hour
        self._od_demands: list[dict] = []        # [{origin, dest, demand_vph}]

    # ------------------------------------------------------------------
    # Demand configuration
    # ------------------------------------------------------------------

    def add_od_demand(
        self,
        origin_node: int,
        dest_node: int,
        demand_vph: float,
    ) -> None:
        """
        Register an origin-destination demand pair.

        Args:
            origin_node: Source node ID (evacuation zone).
            dest_node: Destination node ID (safe zone / shelter).
            demand_vph: Traffic demand in vehicles per hour.
        """
        self._od_demands.append({
            "origin": origin_node,
            "dest": dest_node,
            "demand": demand_vph,
        })

    def generate_od_from_zones(
        self,
        evacuation_nodes: list[int],
        safe_nodes: list[int],
        population_density: float = 1000.0,
        vehicle_occupancy: float = 2.5,
    ) -> None:
        """
        Auto-generate OD demands from evacuation zone nodes to safe nodes.

        Each evacuation node is routed to the nearest safe node.

        Args:
            evacuation_nodes: Nodes in the hazard zone requiring evacuation.
            safe_nodes: Available destination nodes (shelters / safe zones).
            population_density: Estimated people per km² in evacuation zone.
            vehicle_occupancy: Average persons per vehicle.
        """
        if not safe_nodes:
            logger.warning("No safe nodes available for OD generation.")
            return

        G = self.dyn_graph.active_graph()
        for origin in evacuation_nodes:
            # Pick nearest reachable safe node
            dest = self._nearest_safe_node(G, origin, safe_nodes)
            if dest is None:
                continue
            # Approximate demand: assume 1 vehicle per `vehicle_occupancy` people
            demand = population_density / vehicle_occupancy / 10.0  # crude scaling
            self.add_od_demand(origin, dest, demand)

        logger.info(f"Generated {len(self._od_demands)} OD pairs for traffic simulation.")

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def assign_traffic(self) -> dict[tuple, float]:
        """
        Assign all OD demand to shortest paths and accumulate edge volumes.

        Returns:
            {(u, v): flow_vph} — traffic volume per edge.
        """
        G = self.dyn_graph.active_graph()
        self._volume = {}

        for od in self._od_demands:
            origin = od["origin"]
            dest = od["dest"]
            demand = od["demand"]

            try:
                path = nx.shortest_path(G, origin, dest, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                logger.debug(f"No path from {origin} to {dest} — demand unassigned.")
                continue

            for u, v in zip(path, path[1:]):
                self._volume[(u, v)] = self._volume.get((u, v), 0.0) + demand

        logger.info(f"Traffic assigned: {len(self._volume)} edges with non-zero flow.")
        return dict(self._volume)

    def get_vc_ratios(self) -> dict[tuple, float]:
        """
        Compute volume-to-capacity (V/C) ratios for all loaded edges.

        Returns:
            {(u, v): vc_ratio} — ratios >1 indicate over-capacity.
        """
        G = self.dyn_graph.graph
        vc = {}
        for (u, v), vol in self._volume.items():
            if G.has_edge(u, v):
                lanes = G[u][v].get("lanes") or 1
                capacity = lanes * self.default_capacity
                vc[(u, v)] = vol / max(capacity, 1.0)
        return vc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nearest_safe_node(G, origin: int, safe_nodes: list[int]) -> Optional[int]:
        """Return the closest reachable safe node from origin using Dijkstra."""
        try:
            lengths = nx.single_source_dijkstra_path_length(G, origin, weight="weight")
        except nx.NodeNotFound:
            return None
        best, best_len = None, float("inf")
        for node in safe_nodes:
            d = lengths.get(node, float("inf"))
            if d < best_len:
                best_len = d
                best = node
        return best
