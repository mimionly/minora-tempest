"""
flood_risk.py
-------------
Computes per-node and per-edge flood risk scores combining:
- Static terrain risk (low elevation, depression, proximity to water bodies)
- Dynamic simulation output (water depth from water_propagation.py)
- Historical flood frequency (from datasets/disasters/)

Risk scores are normalised to [0.0, 1.0] and used by:
- edge_weights.py (routing penalty)
- risk/risk_propagation.py (area-wide risk maps)
- safe_zone_mapper.py (zone evaluation)
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Thresholds
DEPTH_IMPASSABLE_M = 0.5       # water depth that makes a road impassable
DEPTH_HIGH_RISK_M = 0.3        # depth for high risk rating
PROXIMITY_WATER_BODY_M = 200   # proximity to river/lake for elevated baseline risk


def elevation_risk(elevation_m: Optional[float], sea_level_m: float = 0.0) -> float:
    """
    Static risk component based on elevation above sea level.

    Args:
        elevation_m: Node elevation in metres.
        sea_level_m: Local sea / flood baseline in metres.

    Returns:
        Risk score [0.0, 1.0]. Higher score = more flood-prone.
    """
    if elevation_m is None:
        return 0.5  # unknown → moderate risk
    above = elevation_m - sea_level_m
    if above <= 0:
        return 1.0  # at or below sea level
    if above >= 50:
        return 0.0  # safely elevated
    return 1.0 - (above / 50.0)


def depth_risk(water_depth_m: float) -> float:
    """
    Dynamic risk score from current water depth at a node.

    Args:
        water_depth_m: Simulated water depth in metres.

    Returns:
        Risk score [0.0, 1.0].
    """
    if water_depth_m <= 0:
        return 0.0
    if water_depth_m >= DEPTH_IMPASSABLE_M:
        return 1.0
    return water_depth_m / DEPTH_IMPASSABLE_M


def historical_risk(flood_frequency: float) -> float:
    """
    Risk score from historical flood occurrence rate.

    Args:
        flood_frequency: Fraction of years this area has flooded [0.0, 1.0].

    Returns:
        Risk score [0.0, 1.0].
    """
    return min(max(flood_frequency, 0.0), 1.0)


class FloodRiskScorer:
    """
    Computes composite flood risk scores for all nodes and edges.

    Combines static (terrain) and dynamic (simulation) risk components
    with configurable weights.
    """

    def __init__(
        self,
        elevation_loader,
        node_mapper,
        weight_elevation: float = 0.3,
        weight_depth: float = 0.5,
        weight_historical: float = 0.2,
        sea_level_m: float = 0.0,
    ):
        """
        Args:
            elevation_loader: ElevationLoader instance.
            node_mapper: NodeMapper instance.
            weight_elevation: Weight for terrain elevation component.
            weight_depth: Weight for dynamic water depth component.
            weight_historical: Weight for historical frequency component.
            sea_level_m: Local flood baseline elevation in metres.
        """
        self.loader = elevation_loader
        self.mapper = node_mapper
        self.w_elev = weight_elevation
        self.w_depth = weight_depth
        self.w_hist = weight_historical
        self.sea_level = sea_level_m

    def compute_node_risks(
        self,
        depth_map: dict[int, float],
        historical_map: Optional[dict[int, float]] = None,
    ) -> dict[int, float]:
        """
        Compute flood risk scores for all nodes.

        Args:
            depth_map: {node_id: water_depth_m} from WaterPropagationModel.
            historical_map: {node_id: flood_frequency} from historical data.

        Returns:
            {node_id: risk_score [0.0, 1.0]}
        """
        historical_map = historical_map or {}
        risk_scores: dict[int, float] = {}

        for node_id in depth_map:
            coords = self.mapper.get_node_coords(node_id)
            if coords:
                elev = self.loader.get_elevation(*coords)
            else:
                elev = None

            r_elev = elevation_risk(elev, self.sea_level)
            r_depth = depth_risk(depth_map.get(node_id, 0.0))
            r_hist = historical_risk(historical_map.get(node_id, 0.0))

            composite = (
                self.w_elev * r_elev
                + self.w_depth * r_depth
                + self.w_hist * r_hist
            )
            risk_scores[node_id] = round(min(composite, 1.0), 4)

        logger.info(f"FloodRisk: scored {len(risk_scores)} nodes.")
        return risk_scores

    def compute_edge_risks(
        self, G, node_risk_map: dict[int, float]
    ) -> dict[tuple, float]:
        """
        Derive per-edge risk as the maximum of its endpoint node risks.

        Args:
            G: NetworkX DiGraph.
            node_risk_map: Output of compute_node_risks().

        Returns:
            {(u, v): risk_score}
        """
        edge_risks = {}
        for u, v in G.edges():
            edge_risks[(u, v)] = max(
                node_risk_map.get(u, 0.0),
                node_risk_map.get(v, 0.0),
            )
        return edge_risks
