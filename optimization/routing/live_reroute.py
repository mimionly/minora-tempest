"""
Live Reroute Monitor — Active Ambulance Tracker & Dynamic Rerouter
====================================================================

This is the LOOP that was missing.

It maintains a registry of all active ambulance assignments,
simulates their movement along their assigned path (node by node),
and checks at every step whether the road ahead has become
blocked/risky since they started driving.

If a reroute is needed:
    1. The old remaining path is cleared of congestion
    2. A new A* path is computed from the ambulance's current position
    3. The new path gets congestion applied
    4. The assignment record is updated

Usage (from the orchestrator or a background task):
    monitor = LiveRerouteMonitor(graph)
    monitor.register_assignment(assignment_dict)
    
    # On every simulation tick (or WebSocket update cycle):
    events = monitor.tick()
    # events = list of reroute/arrival/blocked notifications

This module is stateful — it holds the "convoy table" of all
active resource movements.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import networkx as nx

from optimization.types import RouteResult, NodeId
from optimization.routing.rerouting import should_reroute, compute_reroute
from optimization.routing.safe_route import find_safe_route


# ---------------------------------------------------------------------------
# Active Ambulance Tracker
# ---------------------------------------------------------------------------
@dataclass
class ActiveConvoy:
    """Tracks a single ambulance moving along its route."""
    resource_id: str
    incident_id: str
    route: RouteResult
    position_index: int = 0        # Current node index along path_nodes
    reroute_count: int = 0         # How many times this ambulance was rerouted
    status: str = "en_route"       # en_route | arrived | stranded

    @property
    def current_node(self) -> NodeId:
        return self.route.path_nodes[self.position_index]

    @property
    def destination_node(self) -> NodeId:
        return self.route.path_nodes[-1]

    @property
    def remaining_nodes(self) -> List[NodeId]:
        return self.route.path_nodes[self.position_index:]

    @property
    def has_arrived(self) -> bool:
        return self.position_index >= len(self.route.path_nodes) - 1

    def advance(self) -> None:
        """Move the ambulance one node forward along its path."""
        if not self.has_arrived:
            self.position_index += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "incident_id": self.incident_id,
            "current_node": self.current_node,
            "destination_node": self.destination_node,
            "position_index": self.position_index,
            "total_nodes": len(self.route.path_nodes),
            "progress_pct": round(
                self.position_index / max(len(self.route.path_nodes) - 1, 1) * 100, 1
            ),
            "reroute_count": self.reroute_count,
            "status": self.status,
            "remaining_path": self.remaining_nodes,
            "route": self.route.to_dict(),
        }


# ---------------------------------------------------------------------------
# Reroute Monitor (The Loop)
# ---------------------------------------------------------------------------
class LiveRerouteMonitor:
    """
    Maintains a live registry of all moving ambulances and
    checks for rerouting on every tick.

    This is the "heartbeat" of the real-time system.
    In production, this would run on a background asyncio task
    triggered by a WebSocket timer or simulation_service.py tick.
    """

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.convoys: Dict[str, ActiveConvoy] = {}  # resource_id -> ActiveConvoy
        self.event_log: List[Dict[str, Any]] = []
        self._tick_count: int = 0

    @property
    def active_count(self) -> int:
        return sum(1 for c in self.convoys.values() if c.status == "en_route")

    def register_assignment(self, assignment: Dict[str, Any]) -> None:
        """
        Register a new ambulance assignment from dispatch_resources().

        Args:
            assignment: dict with resource_id, incident_id, route (dict)
        """
        route_dict = assignment["route"]
        route = RouteResult(
            path_nodes=route_dict["path_nodes"],
            path_coords=route_dict.get("path_coords", []),
            total_distance_m=route_dict.get("total_distance_m", 0),
            total_cost=route_dict.get("total_cost", 0),
            estimated_time_s=route_dict.get("estimated_time_s", 0),
            risk_score=route_dict.get("risk_score", 0),
            algorithm=route_dict.get("algorithm", "astar"),
            is_fallback=route_dict.get("is_fallback", False),
        )

        convoy = ActiveConvoy(
            resource_id=assignment["resource_id"],
            incident_id=assignment["incident_id"],
            route=route,
            position_index=0,
            status="en_route",
        )

        self.convoys[assignment["resource_id"]] = convoy

        self._log_event("registered", convoy, detail="Ambulance dispatched, tracking started")

    def register_all(self, assignments: List[Dict[str, Any]]) -> None:
        """Register multiple assignments at once."""
        for a in assignments:
            self.register_assignment(a)

    # -----------------------------------------------------------------------
    # THE CORE TICK — called every simulation cycle
    # -----------------------------------------------------------------------
    def tick(self) -> List[Dict[str, Any]]:
        """
        Advance all ambulances by one node, check for reroutes.

        This is the function that runs in a loop.
        Returns a list of events that happened during this tick.

        Event types:
            - "moved":     Ambulance advanced one node
            - "rerouted":  Path was blocked/risky, new route computed
            - "arrived":   Ambulance reached its destination
            - "stranded":  No route exists — ambulance is stuck
        """
        self._tick_count += 1
        tick_events = []

        for resource_id, convoy in list(self.convoys.items()):
            if convoy.status != "en_route":
                continue

            # Step 1: Check if reroute is needed BEFORE moving
            needs_reroute = should_reroute(
                self.graph,
                convoy.route,
                convoy.position_index,
            )

            if needs_reroute:
                # Attempt to compute a new route
                new_route = compute_reroute(
                    self.graph,
                    convoy.route,
                    convoy.position_index,
                )

                if new_route is not None:
                    # Successful reroute
                    convoy.route = new_route
                    convoy.position_index = 0  # reset — new route starts from current node
                    convoy.reroute_count += 1

                    event = self._log_event(
                        "rerouted", convoy,
                        detail=(
                            f"Path blocked/risky ahead. Rerouted via {new_route.algorithm}. "
                            f"New distance: {new_route.total_distance_m:.0f}m, "
                            f"risk: {new_route.risk_score:.3f}. "
                            f"Reroute #{convoy.reroute_count}"
                        ),
                    )
                    tick_events.append(event)
                else:
                    # No alternative route — ambulance is stranded
                    convoy.status = "stranded"
                    event = self._log_event(
                        "stranded", convoy,
                        detail="All routes blocked. No path to destination. Requesting air support.",
                    )
                    tick_events.append(event)
                    continue

            # Step 2: Advance one node
            convoy.advance()

            if convoy.has_arrived:
                convoy.status = "arrived"
                event = self._log_event(
                    "arrived", convoy,
                    detail=f"Ambulance reached incident {convoy.incident_id}.",
                )
                tick_events.append(event)
            else:
                event = self._log_event(
                    "moved", convoy,
                    detail=f"Advanced to node {convoy.current_node}.",
                )
                tick_events.append(event)

        return tick_events

    def run_full_simulation(self, max_ticks: int = 50) -> List[Dict[str, Any]]:
        """
        Run ticks until all ambulances arrive or are stranded.

        This is the demo-friendly version — runs the complete
        simulation in one call and returns all events.
        """
        all_events = []

        for _ in range(max_ticks):
            if self.active_count == 0:
                break
            events = self.tick()
            all_events.extend(events)

        return all_events

    # -----------------------------------------------------------------------
    # Inject road disruption mid-transit (for demo / testing)
    # -----------------------------------------------------------------------
    def block_road(self, node_u: NodeId, node_v: NodeId) -> Dict[str, Any]:
        """
        Block a road segment mid-simulation.

        This simulates a new flood wave or a bridge collapse
        WHILE ambulances are already driving.

        The next tick() call will detect the blockage and reroute.
        """
        if self.graph.has_edge(node_u, node_v):
            edge_data = self.graph[node_u][node_v]
            if isinstance(edge_data, dict) and 0 in edge_data:
                edge_data = edge_data[0]
            edge_data["blocked"] = True
            edge_data["disaster_risk"] = 1.0

        affected = []
        for rid, convoy in self.convoys.items():
            if convoy.status != "en_route":
                continue
            remaining = convoy.remaining_nodes
            for i in range(len(remaining) - 1):
                if (remaining[i] == node_u and remaining[i+1] == node_v) or \
                   (remaining[i] == node_v and remaining[i+1] == node_u):
                    affected.append(rid)
                    break

        return {
            "blocked_edge": (node_u, node_v),
            "affected_ambulances": affected,
            "will_reroute_on_next_tick": len(affected),
        }

    def increase_risk(self, node_u: NodeId, node_v: NodeId, risk: float = 0.9) -> None:
        """Increase disaster risk on a road without fully blocking it."""
        if self.graph.has_edge(node_u, node_v):
            edge_data = self.graph[node_u][node_v]
            if isinstance(edge_data, dict) and 0 in edge_data:
                edge_data = edge_data[0]
            edge_data["disaster_risk"] = min(risk, 1.0)

    # -----------------------------------------------------------------------
    # Status / Reporting
    # -----------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        """Full status of all tracked ambulances."""
        return {
            "tick": self._tick_count,
            "total_tracked": len(self.convoys),
            "active": self.active_count,
            "arrived": sum(1 for c in self.convoys.values() if c.status == "arrived"),
            "stranded": sum(1 for c in self.convoys.values() if c.status == "stranded"),
            "total_reroutes": sum(c.reroute_count for c in self.convoys.values()),
            "convoys": {rid: c.to_dict() for rid, c in self.convoys.items()},
        }

    def get_reroute_summary(self) -> Dict[str, Any]:
        """Summary focused on reroute events for the frontend."""
        rerouted = [c for c in self.convoys.values() if c.reroute_count > 0]
        return {
            "total_reroutes": sum(c.reroute_count for c in self.convoys.values()),
            "ambulances_rerouted": len(rerouted),
            "details": [
                {
                    "resource_id": c.resource_id,
                    "incident_id": c.incident_id,
                    "reroute_count": c.reroute_count,
                    "current_status": c.status,
                }
                for c in rerouted
            ],
        }

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------
    def _log_event(self, event_type: str, convoy: ActiveConvoy, detail: str = "") -> Dict[str, Any]:
        event = {
            "tick": self._tick_count,
            "event": event_type,
            "resource_id": convoy.resource_id,
            "incident_id": convoy.incident_id,
            "current_node": convoy.current_node,
            "position_index": convoy.position_index,
            "reroute_count": convoy.reroute_count,
            "status": convoy.status,
            "detail": detail,
        }
        self.event_log.append(event)
        return event
