"""
risk_propagation.py
-------------------
Aggregates and propagates multi-hazard risk across the road network.

Combines:
- Flood risk scores (from flood/flood_risk.py)
- Wildfire risk scores (derived from FireSpreadSimulator state)
- Congestion risk (from congestion_model.py V/C ratios)

Outputs a unified composite risk score per node and per edge,
used for evacuation routing weight penalties and danger zone marking.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default weights for multi-hazard combination
DEFAULT_WEIGHTS = {
    "flood": 0.4,
    "fire": 0.4,
    "congestion": 0.2,
}


def combine_risks(
    flood: float = 0.0,
    fire: float = 0.0,
    congestion: float = 0.0,
    weights: Optional[dict] = None,
) -> float:
    """
    Weighted sum of individual hazard risk scores.

    Args:
        flood: Flood risk score [0, 1].
        fire: Fire risk score [0, 1].
        congestion: Congestion risk score [0, 1].
        weights: Custom weight dict {flood, fire, congestion}.

    Returns:
        Composite risk score [0, 1].
    """
    w = weights or DEFAULT_WEIGHTS
    score = (
        w.get("flood", 0.4) * flood
        + w.get("fire", 0.4) * fire
        + w.get("congestion", 0.2) * congestion
    )
    return round(min(score, 1.0), 4)


class RiskPropagator:
    """
    Builds and maintains a composite risk map across the road network.

    Supports multi-hazard combination and neighbour-aware propagation:
    a node's risk is influenced by the maximum risk of its k-hop neighbours.
    """

    def __init__(
        self,
        dynamic_graph,
        propagation_decay: float = 0.5,
        max_hops: int = 2,
    ):
        """
        Args:
            dynamic_graph: DynamicGraph with the live road graph.
            propagation_decay: Fraction of neighbour risk inherited per hop (0–1).
            max_hops: Number of hops over which risk propagates.
        """
        self.dyn_graph = dynamic_graph
        self.decay = propagation_decay
        self.max_hops = max_hops
        self._node_risk: dict[int, float] = {}
        self._edge_risk: dict[tuple, float] = {}

    # ------------------------------------------------------------------
    # Risk computation
    # ------------------------------------------------------------------

    def compute(
        self,
        flood_risk_map: Optional[dict] = None,
        fire_risk_map: Optional[dict] = None,
        congestion_map: Optional[dict] = None,
        weights: Optional[dict] = None,
    ) -> dict[int, float]:
        """
        Compute composite risk for every node and propagate to neighbours.

        Args:
            flood_risk_map: {node_id: flood_risk [0,1]}.
            fire_risk_map: {node_id: fire_risk [0,1]}.
            congestion_map: {(u,v): vc_ratio [0,1+]}.
            weights: Custom hazard weights dict.

        Returns:
            {node_id: composite_risk}
        """
        flood_risk_map = flood_risk_map or {}
        fire_risk_map = fire_risk_map or {}
        congestion_map = congestion_map or {}
        G = self.dyn_graph.graph

        # Convert edge congestion to node congestion (max of incident edges)
        node_congestion: dict[int, float] = {}
        for (u, v), vc in congestion_map.items():
            cong_score = min(vc, 1.0)
            node_congestion[u] = max(node_congestion.get(u, 0.0), cong_score)
            node_congestion[v] = max(node_congestion.get(v, 0.0), cong_score)

        # Base composite risk per node
        base_risk: dict[int, float] = {}
        for node in G.nodes():
            base_risk[node] = combine_risks(
                flood=flood_risk_map.get(node, 0.0),
                fire=fire_risk_map.get(node, 0.0),
                congestion=node_congestion.get(node, 0.0),
                weights=weights,
            )

        # Propagate risk to neighbours
        self._node_risk = self._propagate(G, base_risk)
        self._edge_risk = self._derive_edge_risk(G)

        logger.info(
            f"RiskPropagator: computed risk for {len(self._node_risk)} nodes."
        )
        return dict(self._node_risk)

    def get_edge_risks(self) -> dict[tuple, float]:
        """Return per-edge risk map (max of endpoint node risks)."""
        return dict(self._edge_risk)

    def high_risk_nodes(self, threshold: float = 0.6) -> list[int]:
        """Return nodes with composite risk above the threshold."""
        return [n for n, r in self._node_risk.items() if r >= threshold]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _propagate(self, G, base_risk: dict[int, float]) -> dict[int, float]:
        """
        Iteratively propagate risk from high-risk nodes to neighbours.
        Each hop applies a decay factor.
        """
        risk = dict(base_risk)
        for _ in range(self.max_hops):
            new_risk = dict(risk)
            for node in G.nodes():
                neighbour_max = max(
                    (risk.get(nb, 0.0) for nb in G.predecessors(node)),
                    default=0.0,
                )
                propagated = neighbour_max * self.decay
                new_risk[node] = round(min(max(risk.get(node, 0.0), propagated), 1.0), 4)
            risk = new_risk
        return risk

    def _derive_edge_risk(self, G) -> dict[tuple, float]:
        """Edge risk = max of source and target node risk."""
        return {
            (u, v): max(self._node_risk.get(u, 0.0), self._node_risk.get(v, 0.0))
            for u, v in G.edges()
        }
