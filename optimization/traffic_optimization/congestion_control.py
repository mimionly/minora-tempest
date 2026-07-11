"""
Congestion Control — City-Wide Traffic Monitoring
===================================================

Monitors the overall traffic state of the city graph and
detects gridlock situations before they become critical.

Provides reports for:
    - Person 3's dashboard API
    - Traffic Agent decision-making
    - Explanation Agent's rationale
"""

from typing import List, Dict, Any, Tuple

import networkx as nx

from optimization.types import NodeId


# Thresholds
CONGESTION_WARNING = 0.5       # 50% — yellow on dashboard
CONGESTION_CRITICAL = 0.8      # 80% — red on dashboard
GRIDLOCK_RATIO_THRESHOLD = 0.3 # 30% of edges critical = gridlock


def get_congestion_report(graph: nx.Graph) -> Dict[str, Any]:
    """
    Generate a city-wide congestion report.

    Returns a dict with:
        - total_edges: int
        - congested_edges: int (above warning threshold)
        - critical_edges: int (above critical threshold)
        - average_congestion: float
        - max_congestion: float
        - gridlock_detected: bool
        - hotspot_nodes: list of most congested node IDs
        - status: "normal" | "elevated" | "critical" | "gridlock"
    """
    total = 0
    congested = 0
    critical = 0
    total_congestion = 0.0
    max_congestion = 0.0
    node_congestion: Dict[NodeId, float] = {}

    for u, v, data in graph.edges(data=True):
        edge_data = data
        if isinstance(data, dict) and 0 in data:
            edge_data = data[0]

        cong = edge_data.get("congestion", 0.0)
        total += 1
        total_congestion += cong
        max_congestion = max(max_congestion, cong)

        if cong >= CONGESTION_WARNING:
            congested += 1
        if cong >= CONGESTION_CRITICAL:
            critical += 1

        # Track per-node congestion (average of incident edges)
        for node in (u, v):
            if node not in node_congestion:
                node_congestion[node] = 0.0
            node_congestion[node] = max(node_congestion[node], cong)

    avg_congestion = total_congestion / max(total, 1)

    # Detect gridlock
    critical_ratio = critical / max(total, 1)
    gridlock = critical_ratio >= GRIDLOCK_RATIO_THRESHOLD

    # Determine status
    if gridlock:
        status = "gridlock"
    elif critical > 0:
        status = "critical"
    elif congested > 0:
        status = "elevated"
    else:
        status = "normal"

    # Find hotspot nodes (top 10 most congested)
    sorted_nodes = sorted(
        node_congestion.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    hotspots = [
        {"node_id": node, "congestion": round(cong, 3)}
        for node, cong in sorted_nodes[:10]
        if cong >= CONGESTION_WARNING
    ]

    return {
        "total_edges": total,
        "congested_edges": congested,
        "critical_edges": critical,
        "average_congestion": round(avg_congestion, 4),
        "max_congestion": round(max_congestion, 4),
        "gridlock_detected": gridlock,
        "hotspot_nodes": hotspots,
        "status": status,
    }


def detect_gridlock(graph: nx.Graph) -> bool:
    """
    Quick check: is the city in gridlock?

    Returns True if more than 30% of edges are critically congested.
    """
    report = get_congestion_report(graph)
    return report["gridlock_detected"]


def get_congested_edges(
    graph: nx.Graph,
    threshold: float = CONGESTION_WARNING,
) -> List[Tuple[NodeId, NodeId, float]]:
    """
    Return all edges above a congestion threshold.

    Useful for highlighting on the map.

    Returns:
        List of (u, v, congestion_value) tuples.
    """
    result = []

    for u, v, data in graph.edges(data=True):
        edge_data = data
        if isinstance(data, dict) and 0 in data:
            edge_data = data[0]

        cong = edge_data.get("congestion", 0.0)
        if cong >= threshold:
            result.append((u, v, round(cong, 3)))

    result.sort(key=lambda x: x[2], reverse=True)
    return result


def auto_relieve_congestion(
    graph: nx.Graph,
    decay_rate: float = 0.05,
) -> int:
    """
    Naturally decay congestion over time.

    Call this periodically (e.g., every simulation tick)
    to simulate traffic clearing on unused roads.

    Args:
        graph:      City graph
        decay_rate: How much congestion decreases per tick

    Returns:
        Number of edges that had congestion reduced.
    """
    relieved = 0

    for u, v, data in graph.edges(data=True):
        edge_data = data
        if isinstance(data, dict) and 0 in data:
            edge_data = data[0]

        current = edge_data.get("congestion", 0.0)
        if current > 0:
            edge_data["congestion"] = max(0.0, current - decay_rate)
            relieved += 1

    return relieved
