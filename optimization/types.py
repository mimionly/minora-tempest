"""
Shared type definitions for the Optimization Engine.

All modules in Person 2's domain use these data structures
to communicate results. Person 3 (Backend) consumes these
via .to_dict() for JSON serialization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Coordinates
# ---------------------------------------------------------------------------
Coord = Tuple[float, float]  # (latitude, longitude)
NodeId = int                  # NetworkX node identifier


# ---------------------------------------------------------------------------
# Resource Types
# ---------------------------------------------------------------------------
class ResourceType(str, Enum):
    AMBULANCE = "ambulance"
    FIRE_TRUCK = "fire_truck"
    RESCUE_BOAT = "rescue_boat"
    OXYGEN_TRUCK = "oxygen_truck"
    FOOD_VAN = "food_van"
    POLICE = "police"


class ResourceStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    RETURNING = "returning"
    OUT_OF_SERVICE = "out_of_service"


class UrgencyLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Route Result
# ---------------------------------------------------------------------------
@dataclass
class RouteResult:
    """Output of any routing algorithm."""
    path_nodes: List[NodeId]            # Ordered list of graph node IDs
    path_coords: List[Coord]            # Ordered list of (lat, lon)
    total_distance_m: float             # Total distance in meters
    total_cost: float                   # Composite cost (distance + risk + congestion)
    estimated_time_s: float             # Estimated travel time in seconds
    risk_score: float                   # Average risk along the route (0.0–1.0)
    algorithm: str                      # "astar" | "dijkstra"
    is_fallback: bool = False           # True if no safe route found, using best-effort

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_nodes": self.path_nodes,
            "path_coords": self.path_coords,
            "total_distance_m": round(self.total_distance_m, 2),
            "total_cost": round(self.total_cost, 2),
            "estimated_time_s": round(self.estimated_time_s, 2),
            "risk_score": round(self.risk_score, 4),
            "algorithm": self.algorithm,
            "is_fallback": self.is_fallback,
        }


# ---------------------------------------------------------------------------
# Resource
# ---------------------------------------------------------------------------
@dataclass
class Resource:
    """A simulated emergency resource unit."""
    resource_id: str
    resource_type: ResourceType
    current_coords: Coord
    current_node: Optional[NodeId] = None
    status: ResourceStatus = ResourceStatus.AVAILABLE
    capacity: int = 1
    speed_kmh: float = 40.0
    assigned_incident: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "current_coords": list(self.current_coords),
            "current_node": self.current_node,
            "status": self.status.value,
            "capacity": self.capacity,
            "speed_kmh": self.speed_kmh,
            "assigned_incident": self.assigned_incident,
        }


# ---------------------------------------------------------------------------
# Incident / Help Request
# ---------------------------------------------------------------------------
@dataclass
class Incident:
    """A disaster incident or civilian SOS request."""
    incident_id: str
    coords: Coord
    nearest_node: Optional[NodeId] = None
    severity: float = 0.5              # 0.0–1.0
    people_affected: int = 1
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    requires_type: Optional[ResourceType] = None
    is_resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "coords": list(self.coords),
            "nearest_node": self.nearest_node,
            "severity": self.severity,
            "people_affected": self.people_affected,
            "urgency": self.urgency.value,
            "requires_type": self.requires_type.value if self.requires_type else None,
            "is_resolved": self.is_resolved,
        }


# ---------------------------------------------------------------------------
# Assignment (output of resource allocation)
# ---------------------------------------------------------------------------
@dataclass
class Assignment:
    """Binds a resource to an incident with a planned route."""
    resource_id: str
    incident_id: str
    route: RouteResult
    priority_rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "incident_id": self.incident_id,
            "route": self.route.to_dict(),
            "priority_rank": self.priority_rank,
        }


# ---------------------------------------------------------------------------
# Rescue Queue Item
# ---------------------------------------------------------------------------
@dataclass
class RescueTask:
    """A single task in the rescue priority queue."""
    incident_id: str
    urgency_score: float               # Higher = more urgent
    coords: Coord
    people_affected: int
    urgency_level: UrgencyLevel
    assigned_resource: Optional[str] = None
    eta_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "urgency_score": round(self.urgency_score, 4),
            "coords": list(self.coords),
            "people_affected": self.people_affected,
            "urgency_level": self.urgency_level.value,
            "assigned_resource": self.assigned_resource,
            "eta_seconds": round(self.eta_seconds, 2) if self.eta_seconds else None,
        }


# ---------------------------------------------------------------------------
# Scoring Results
# ---------------------------------------------------------------------------
@dataclass
class ZoneScore:
    """Vulnerability/risk score for a geographic zone."""
    zone_id: str
    coords: Coord
    vulnerability_score: float         # 0.0–1.0
    population_density: float
    risk_level: float
    hospital_load: float               # 0.0–1.0 (1.0 = overloaded)
    shelter_occupancy: float            # 0.0–1.0 (1.0 = full)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "coords": list(self.coords),
            "vulnerability_score": round(self.vulnerability_score, 4),
            "population_density": round(self.population_density, 2),
            "risk_level": round(self.risk_level, 4),
            "hospital_load": round(self.hospital_load, 4),
            "shelter_occupancy": round(self.shelter_occupancy, 4),
        }
