"""
blocked_roads.py
----------------
Maintains the registry of roads blocked by disaster events and
applies / reverts blockages on the DynamicGraph.

Blocked roads may result from:
- Flood inundation (flood_spread.py)
- Wildfire burn (fire_spread.py)
- Physical damage / debris (external reports)
- Traffic gridlock (congestion_model.py gridlocked_edges)
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class BlockReason(str, Enum):
    FLOOD = "FLOOD"
    WILDFIRE = "WILDFIRE"
    DEBRIS = "DEBRIS"
    GRIDLOCK = "GRIDLOCK"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    MANUAL = "MANUAL"


class BlockedRoadRegistry:
    """
    Tracks which road edges are blocked and why.

    Provides batch block/unblock operations and reason-aware queries.
    """

    def __init__(self, dynamic_graph):
        """
        Args:
            dynamic_graph: DynamicGraph instance to apply blockages on.
        """
        self.dyn_graph = dynamic_graph
        self._blocks: dict[tuple, list[BlockReason]] = {}  # (u,v) → reasons

    # ------------------------------------------------------------------
    # Block / unblock
    # ------------------------------------------------------------------

    def block(
        self,
        u: int,
        v: int,
        reason: BlockReason = BlockReason.MANUAL,
        bidirectional: bool = False,
    ) -> None:
        """
        Block a road edge.

        Args:
            u: Source node.
            v: Target node.
            reason: Reason for the blockage.
            bidirectional: Also block the reverse edge (v → u).
        """
        self._add_block(u, v, reason)
        self.dyn_graph.block_edge(u, v)
        if bidirectional:
            self._add_block(v, u, reason)
            self.dyn_graph.block_edge(v, u)

    def unblock(self, u: int, v: int, reason: Optional[BlockReason] = None) -> None:
        """
        Remove a blockage (optionally only for a specific reason).

        If a reason is given, only that reason is removed. The edge stays
        blocked if other reasons remain.

        Args:
            u: Source node.
            v: Target node.
            reason: If provided, only remove this reason; else clear all.
        """
        key = (u, v)
        if key not in self._blocks:
            return
        if reason is None:
            del self._blocks[key]
            self.dyn_graph.unblock_edge(u, v)
        else:
            reasons = self._blocks[key]
            if reason in reasons:
                reasons.remove(reason)
            if not reasons:
                del self._blocks[key]
                self.dyn_graph.unblock_edge(u, v)

    def block_batch(
        self,
        edges: list[tuple],
        reason: BlockReason = BlockReason.MANUAL,
    ) -> None:
        """
        Block multiple edges at once.

        Args:
            edges: List of (u, v) tuples.
            reason: Reason applied to all edges.
        """
        for u, v in edges:
            self.block(u, v, reason)
        logger.info(f"Blocked {len(edges)} edges (reason: {reason}).")

    def unblock_by_reason(self, reason: BlockReason) -> int:
        """
        Unblock all edges with a specific reason (e.g. flood receding).

        Returns:
            Number of edges fully unblocked.
        """
        fully_unblocked = 0
        for (u, v) in list(self._blocks.keys()):
            self.unblock(u, v, reason)
            if (u, v) not in self._blocks:
                fully_unblocked += 1
        logger.info(f"Unblocked {fully_unblocked} edges with reason {reason}.")
        return fully_unblocked

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_blocked(self, u: int, v: int) -> bool:
        return (u, v) in self._blocks

    def all_blocked_edges(self) -> list[tuple]:
        return list(self._blocks.keys())

    def blocked_by_reason(self, reason: BlockReason) -> list[tuple]:
        return [(u, v) for (u, v), reasons in self._blocks.items() if reason in reasons]

    def summary(self) -> dict:
        counts: dict[str, int] = {r.value: 0 for r in BlockReason}
        for reasons in self._blocks.values():
            for r in reasons:
                counts[r.value] += 1
        return {"total_blocked": len(self._blocks), **counts}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_block(self, u: int, v: int, reason: BlockReason) -> None:
        key = (u, v)
        if key not in self._blocks:
            self._blocks[key] = []
        if reason not in self._blocks[key]:
            self._blocks[key].append(reason)
