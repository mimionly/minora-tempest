"""
water_propagation.py
--------------------
Models shallow water flow dynamics across the terrain DEM.

Uses a simplified kinematic wave model:
- Water accumulates in low-lying areas
- Propagation speed depends on slope (Manning's equation approximation)
- Outputs per-cell water depth over time
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Manning's roughness coefficients (n) for surface types
MANNING_N = {
    "road": 0.016,
    "grass": 0.035,
    "forest": 0.120,
    "urban": 0.025,
    "bare_soil": 0.020,
    "water": 0.012,
}

# Gravity constant (m/s²)
G = 9.81


def flow_velocity(slope: float, depth_m: float, surface: str = "road") -> float:
    """
    Estimate shallow-water flow velocity using Manning's equation.

    V = (1/n) * R^(2/3) * S^(1/2)
    For shallow overland flow: hydraulic radius ≈ depth

    Args:
        slope: Terrain slope in degrees.
        depth_m: Water depth in metres.
        surface: Surface type key from MANNING_N.

    Returns:
        Flow velocity in m/s.
    """
    n = MANNING_N.get(surface, 0.030)
    S = math.tan(math.radians(slope))  # slope as fraction
    if S <= 0 or depth_m <= 0:
        return 0.0
    R = depth_m  # hydraulic radius = depth for wide shallow flow
    return (1.0 / n) * (R ** (2 / 3)) * (S ** 0.5)


def travel_time_seconds(distance_m: float, slope: float, depth_m: float, surface: str = "road") -> float:
    """
    Estimate time for water to travel a given distance.

    Args:
        distance_m: Distance to travel in metres.
        slope: Terrain slope in degrees.
        depth_m: Water depth in metres.
        surface: Surface type.

    Returns:
        Travel time in seconds (inf if no flow).
    """
    v = flow_velocity(slope, depth_m, surface)
    if v <= 0:
        return float("inf")
    return distance_m / v


class WaterPropagationModel:
    """
    Simulates water propagation across nodes of the road/terrain graph.

    Maintains a depth map {node_id: depth_m} updated each time step.
    """

    def __init__(
        self,
        node_mapper,
        elevation_loader,
        slope_map: dict,
        time_step_s: float = 300.0,
    ):
        """
        Args:
            node_mapper: NodeMapper for node coordinate lookups.
            elevation_loader: ElevationLoader for elevation queries.
            slope_map: {(u, v): slope_degrees} from SlopeAnalyzer.get_slope_map().
            time_step_s: Simulation time step in seconds (default 5 min).
        """
        self.mapper = node_mapper
        self.loader = elevation_loader
        self.slope_map = slope_map
        self.dt = time_step_s
        self._depth: dict[int, float] = {}     # node_id → current water depth (m)
        self._cumulative_time = 0.0

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialise_depth(self, source_nodes: dict[int, float]) -> None:
        """
        Set initial water depths at source nodes.

        Args:
            source_nodes: {node_id: initial_depth_m}
        """
        self._depth = dict(source_nodes)
        self._cumulative_time = 0.0
        logger.info(f"WaterPropagation: initialised {len(source_nodes)} source nodes.")

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def step(self, G) -> dict[int, float]:
        """
        Advance water propagation by one time step.

        Args:
            G: NetworkX DiGraph (active_graph from DynamicGraph).

        Returns:
            Updated depth map {node_id: depth_m}.
        """
        new_depth = dict(self._depth)

        for u, v, data in G.edges(data=True):
            depth_u = self._depth.get(u, 0.0)
            if depth_u <= 0:
                continue

            slope = self.slope_map.get((u, v), 0.0)
            dist = data.get("length_m", 1.0)
            highway = data.get("highway", "road")
            surface = "road" if highway else "grass"

            v_ms = flow_velocity(slope, depth_u, surface)
            transported = min(depth_u, v_ms * self.dt / max(dist, 1.0) * depth_u)

            new_depth[u] = max(0.0, new_depth.get(u, 0.0) - transported)
            new_depth[v] = new_depth.get(v, 0.0) + transported

        self._depth = new_depth
        self._cumulative_time += self.dt

        total_depth = sum(self._depth.values())
        logger.debug(
            f"[Water t={self._cumulative_time:.0f}s] "
            f"total depth across nodes: {total_depth:.2f}m"
        )
        return dict(self._depth)

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def depth_map(self) -> dict[int, float]:
        return dict(self._depth)

    def nodes_above_threshold(self, threshold_m: float = 0.3) -> list[int]:
        """Return node IDs where water depth exceeds the given threshold."""
        return [n for n, d in self._depth.items() if d >= threshold_m]
