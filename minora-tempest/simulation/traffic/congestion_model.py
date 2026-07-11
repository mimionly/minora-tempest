"""
congestion_model.py
-------------------
Computes traffic congestion levels from V/C ratios and updates
dynamic edge weights in the road graph.

Implements the Bureau of Public Roads (BPR) travel-time function:
    t(v) = t0 * (1 + α * (v/c)^β)

Default BPR parameters: α = 0.15, β = 4 (standard values).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# BPR function parameters
BPR_ALPHA = 0.15
BPR_BETA = 4


def bpr_travel_time(
    free_flow_time_s: float,
    volume: float,
    capacity: float,
    alpha: float = BPR_ALPHA,
    beta: float = BPR_BETA,
) -> float:
    """
    BPR congested travel time.

    Args:
        free_flow_time_s: Free-flow travel time in seconds.
        volume: Traffic flow in vehicles/hour.
        capacity: Road capacity in vehicles/hour.
        alpha: BPR alpha coefficient (default 0.15).
        beta: BPR beta exponent (default 4).

    Returns:
        Congested travel time in seconds.
    """
    if capacity <= 0:
        return float("inf")
    vc = volume / capacity
    return free_flow_time_s * (1 + alpha * (vc ** beta))


def congestion_level(volume: float, capacity: float) -> float:
    """
    Normalised congestion level [0.0, 1.0+].

    Args:
        volume: Traffic flow in vehicles/hour.
        capacity: Road capacity in vehicles/hour.

    Returns:
        V/C ratio (may exceed 1.0 in oversaturated conditions).
    """
    if capacity <= 0:
        return 1.0
    return volume / capacity


class CongestionModel:
    """
    Applies BPR-based congestion updates to graph edge weights.

    Reads V/C ratios from TrafficSimulator.get_vc_ratios() and
    propagates congested travel times back into the DynamicGraph.
    """

    def __init__(
        self,
        dynamic_graph,
        default_lane_capacity_vph: int = 1200,
        alpha: float = BPR_ALPHA,
        beta: float = BPR_BETA,
    ):
        """
        Args:
            dynamic_graph: DynamicGraph with the live road graph.
            default_lane_capacity_vph: Fallback capacity per lane.
            alpha: BPR alpha parameter.
            beta: BPR beta exponent.
        """
        self.dyn_graph = dynamic_graph
        self.default_capacity = default_lane_capacity_vph
        self.alpha = alpha
        self.beta = beta
        self._congestion_map: dict[tuple, float] = {}

    def apply_vc_ratios(self, vc_ratios: dict[tuple, float]) -> dict[tuple, float]:
        """
        Update edge travel-time weights from V/C ratios.

        Args:
            vc_ratios: {(u, v): vc_ratio} from TrafficSimulator.get_vc_ratios().

        Returns:
            {(u, v): congested_travel_time_s}
        """
        G = self.dyn_graph.graph
        updated: dict[tuple, float] = {}
        self._congestion_map = {}

        for (u, v), vc in vc_ratios.items():
            if not G.has_edge(u, v):
                continue
            data = G[u][v]
            t0 = data.get("travel_time_s", 60.0)
            lanes = data.get("lanes") or 1
            capacity = lanes * self.default_capacity

            # BPR: derive volume from vc ratio and capacity
            volume = vc * capacity
            t_cong = bpr_travel_time(t0, volume, capacity, self.alpha, self.beta)

            self.dyn_graph.update_edge_weight(u, v, t_cong)
            updated[(u, v)] = t_cong
            self._congestion_map[(u, v)] = vc

        logger.info(f"CongestionModel: updated weights for {len(updated)} edges.")
        return updated

    def get_congestion_map(self) -> dict[tuple, float]:
        """Return the last computed V/C ratio map."""
        return dict(self._congestion_map)

    def congested_edges(self, threshold: float = 0.85) -> list[tuple]:
        """
        Return edges where V/C ratio exceeds a threshold.

        Args:
            threshold: V/C ratio above which an edge is considered congested.

        Returns:
            List of edge tuples (u, v).
        """
        return [(u, v) for (u, v), vc in self._congestion_map.items() if vc >= threshold]

    def gridlocked_edges(self) -> list[tuple]:
        """Return edges where V/C ≥ 1.0 (at or over capacity)."""
        return self.congested_edges(threshold=1.0)
