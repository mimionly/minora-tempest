"""
edge_weights.py
---------------
Computes and updates edge weights on the road graph.

Weights account for:
- Base travel time (distance / speed)
- Slope penalty (from terrain/slope_analysis.py)
- Flood risk penalty (from simulation/flood/flood_risk.py)
- Traffic congestion multiplier (from simulation/traffic/congestion_model.py)
"""

import logging
import math
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weight component functions
# ---------------------------------------------------------------------------

def travel_time_weight(length_m: float, speed_kmh: float) -> float:
    """
    Base travel-time weight in seconds.

    Args:
        length_m: Edge length in metres.
        speed_kmh: Legal or assumed speed in km/h.

    Returns:
        Travel time in seconds.
    """
    if speed_kmh <= 0:
        return float("inf")
    return (length_m / 1000.0) / speed_kmh * 3600.0


def slope_penalty(slope_degrees: float, base_time_s: float) -> float:
    """
    Multiplicative penalty for steep slopes (affects evacuation speed).

    Args:
        slope_degrees: Terrain slope in degrees [0, 90].
        base_time_s: Base travel time in seconds.

    Returns:
        Adjusted travel time in seconds.
    """
    # Penalty grows quadratically: 0° → ×1.0, 15° → ×1.5, 30° → ×3.0
    factor = 1.0 + (slope_degrees / 30.0) ** 2
    return base_time_s * factor


def flood_risk_penalty(
    risk_score: float,
    base_time_s: float,
    impassable_threshold: float = 0.9,
) -> float:
    """
    Add travel-time penalty proportional to flood risk on the segment.

    Args:
        risk_score: Normalised flood risk [0.0, 1.0].
        base_time_s: Base travel time in seconds.
        impassable_threshold: Risk above this value marks the edge impassable.

    Returns:
        Adjusted time, or inf if impassable.
    """
    if risk_score >= impassable_threshold:
        return float("inf")
    return base_time_s * (1.0 + risk_score * 5.0)


def congestion_multiplier(congestion_level: float, base_time_s: float) -> float:
    """
    Scale travel time by a congestion factor.

    Args:
        congestion_level: Congestion ratio [0.0 = free flow, 1.0 = gridlock].
        base_time_s: Base travel time in seconds.

    Returns:
        Congested travel time in seconds.
    """
    # BPR (Bureau of Public Roads) function: t = t0 * (1 + 0.15*(v/c)^4)
    return base_time_s * (1.0 + 0.15 * (congestion_level ** 4))


# ---------------------------------------------------------------------------
# EdgeWeightCalculator — applies all penalties to a graph
# ---------------------------------------------------------------------------

class EdgeWeightCalculator:
    """
    Iterates over all edges in a NetworkX graph and computes
    a composite 'weight' attribute used for routing algorithms.
    """

    def __init__(
        self,
        slope_data: Optional[dict] = None,
        flood_risk_data: Optional[dict] = None,
        congestion_data: Optional[dict] = None,
    ):
        """
        Args:
            slope_data: Dict mapping edge (u, v) → slope_degrees.
            flood_risk_data: Dict mapping edge (u, v) → risk_score [0,1].
            congestion_data: Dict mapping edge (u, v) → congestion_level [0,1].
        """
        self.slope_data = slope_data or {}
        self.flood_risk_data = flood_risk_data or {}
        self.congestion_data = congestion_data or {}

    def apply(self, G) -> None:
        """
        Compute composite weights for all edges in-place.

        Args:
            G: NetworkX DiGraph produced by GraphBuilder.
        """
        for u, v, data in G.edges(data=True):
            key = (u, v)
            length_m = data.get("length_m", 0.0)
            speed_kmh = data.get("maxspeed", 50)

            w = travel_time_weight(length_m, speed_kmh)
            w = slope_penalty(self.slope_data.get(key, 0.0), w)
            w = flood_risk_penalty(self.flood_risk_data.get(key, 0.0), w)
            w = congestion_multiplier(self.congestion_data.get(key, 0.0), w)

            data["weight"] = round(w, 4)

        logger.info("Edge weights computed and applied to graph.")
