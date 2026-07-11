"""Traffic optimization subpackage — congestion control and emergency corridors."""

from optimization.traffic_optimization.emergency_corridors import create_emergency_corridor
from optimization.traffic_optimization.traffic_rerouting import reroute_civilian_traffic
from optimization.traffic_optimization.edge_penalties import update_edge_penalties, reset_penalties
from optimization.traffic_optimization.congestion_control import (
    get_congestion_report,
    detect_gridlock,
)

__all__ = [
    "create_emergency_corridor",
    "reroute_civilian_traffic",
    "update_edge_penalties",
    "reset_penalties",
    "get_congestion_report",
    "detect_gridlock",
]
