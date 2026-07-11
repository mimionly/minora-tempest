import { Vehicle, RouteResult } from "../graph/types";
import { RoutingEngine } from "./RoutingEngine";
import { CONFIG } from "../config";

interface DispatchScore {
  vehicle: Vehicle;
  route: RouteResult;
  score: number;
}

/**
 * Weighted-greedy dispatch (Section 8.6) — deliberately NOT globally optimal
 * (that would need OR-Tools/VRP solving). Stated as a scope choice, not a gap.
 */
export class DispatchEngine {
  constructor(private routing: RoutingEngine) {}

  /** Picks the best suitable, available vehicle for an incident at incidentNodeId. */
  dispatch(vehicles: Vehicle[], incidentNodeId: string, requiresDeepWater = false): DispatchScore | null {
    const suitable = vehicles.filter((v) => {
      if (v.status !== "available") return false;
      if (requiresDeepWater) return v.type === "boat" || v.type === "truck";
      return true;
    });

    if (suitable.length === 0) return null;

    let best: DispatchScore | null = null;

    for (const vehicle of suitable) {
      const clearance = CONFIG.VEHICLE_CLEARANCE_CM[vehicle.type];
      const route = this.routing.findRoute(vehicle.position_node, incidentNodeId, clearance);
      if (route.error) continue;

      // Normalize travel time against a 30-min worst case for scoring
      const travelTimeNorm = 1 - Math.min(route.estimated_time_s / 1800, 1);
      const suitability = requiresDeepWater ? (vehicle.type === "boat" ? 1 : 0.6) : 1;
      const availability = 1; // already filtered to available; placeholder for future fleet-load balancing

      const score = travelTimeNorm * 0.5 + suitability * 0.3 + availability * 0.2;

      if (!best || score > best.score) {
        best = { vehicle, route, score: Math.round(score * 1000) / 1000 };
      }
    }

    return best;
  }
}