"""
dynamic_graph.py
----------------
Provides a DynamicGraph wrapper around a static NetworkX DiGraph.

Supports real-time edge blocking, weight updates, and event-driven
modifications triggered by flood/wildfire/traffic simulations.
"""

import logging
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    import networkx as nx
except ImportError as e:
    raise ImportError("NetworkX is required: pip install networkx") from e


class DynamicGraph:
    """
    Wraps a NetworkX DiGraph and tracks dynamic changes:
    - Blocked edges (flooded / collapsed roads)
    - Updated edge weights (changing conditions)
    - Snapshots for time-series replay
    """

    def __init__(self, base_graph: "nx.DiGraph"):
        """
        Args:
            base_graph: Fully-built graph from GraphBuilder.
        """
        self._G = base_graph
        self._blocked_edges: Set[Tuple] = set()
        self._snapshots: list[dict] = []

    # ------------------------------------------------------------------
    # Graph access
    # ------------------------------------------------------------------

    @property
    def graph(self) -> "nx.DiGraph":
        """Return the live graph (with blocked edges removed as virtual weights)."""
        return self._G

    def active_graph(self) -> "nx.DiGraph":
        """
        Return a view of the graph with blocked edges excluded.
        Safe for shortest-path queries.
        """
        G_view = self._G.copy()
        G_view.remove_edges_from(self._blocked_edges)
        return G_view

    # ------------------------------------------------------------------
    # Edge blocking
    # ------------------------------------------------------------------

    def block_edge(self, u, v) -> None:
        """
        Mark an edge as blocked (impassable).

        Args:
            u: Source node ID.
            v: Target node ID.
        """
        self._blocked_edges.add((u, v))
        if self._G.has_edge(u, v):
            self._G[u][v]["weight"] = float("inf")
            self._G[u][v]["blocked"] = True
        logger.debug(f"Edge ({u} → {v}) blocked.")

    def unblock_edge(self, u, v) -> None:
        """
        Restore a previously blocked edge.

        Args:
            u: Source node ID.
            v: Target node ID.
        """
        self._blocked_edges.discard((u, v))
        if self._G.has_edge(u, v):
            self._G[u][v].pop("blocked", None)
            # Weight will be recalculated by EdgeWeightCalculator on next run
        logger.debug(f"Edge ({u} → {v}) unblocked.")

    def block_edges_batch(self, edge_list: list[tuple]) -> None:
        """Block multiple edges at once."""
        for u, v in edge_list:
            self.block_edge(u, v)

    @property
    def blocked_edges(self) -> Set[Tuple]:
        """Return the set of currently blocked edges."""
        return frozenset(self._blocked_edges)

    # ------------------------------------------------------------------
    # Weight updates
    # ------------------------------------------------------------------

    def update_edge_weight(self, u, v, weight: float) -> None:
        """
        Overwrite the composite weight for a single edge.

        Args:
            u: Source node ID.
            v: Target node ID.
            weight: New composite weight value.
        """
        if self._G.has_edge(u, v):
            self._G[u][v]["weight"] = weight
        else:
            logger.warning(f"Cannot update weight: edge ({u}, {v}) not in graph.")

    def update_weights_batch(self, weight_map: dict[tuple, float]) -> None:
        """
        Batch-update edge weights from a dict {(u, v): weight}.

        Args:
            weight_map: Mapping of edge tuples to new composite weights.
        """
        for (u, v), w in weight_map.items():
            self.update_edge_weight(u, v, w)
        logger.info(f"Batch-updated {len(weight_map)} edge weights.")

    # ------------------------------------------------------------------
    # Snapshot / replay
    # ------------------------------------------------------------------

    def save_snapshot(self, timestamp: str, metadata: Optional[dict] = None) -> None:
        """
        Capture the current set of blocked edges as a labelled snapshot.

        Args:
            timestamp: ISO-8601 timestamp string.
            metadata: Optional dict of extra context (e.g., flood stage).
        """
        self._snapshots.append({
            "timestamp": timestamp,
            "blocked": list(self._blocked_edges),
            "metadata": metadata or {},
        })
        logger.info(f"Snapshot saved at {timestamp}: {len(self._blocked_edges)} blocked edges.")

    def get_snapshots(self) -> list[dict]:
        """Return all saved snapshots in chronological order."""
        return self._snapshots
