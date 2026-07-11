import { DecisionExplanation, RouteResult } from "../graph/types";

/**
 * Rule-based explanation engine (Section 8.7) — the PRIMARY explanation
 * mechanism. No AI dependency; instant, reliable, always available.
 */
export class DecisionEngine {
  explain(
    previousRoute: RouteResult | null,
    newRoute: RouteResult,
    blockedRoadName: string | null
  ): DecisionExplanation {
    const riskBefore = previousRoute?.avg_risk_score ?? 0;
    const riskAfter = newRoute.avg_risk_score;

    const delaySaved = previousRoute
      ? Math.max(0, previousRoute.estimated_time_s - newRoute.estimated_time_s)
      : 0;

    let reason: string;
    if (blockedRoadName) {
      reason = `Road ${blockedRoadName} blocked — rerouted to avoid it`;
    } else if (previousRoute && riskAfter < riskBefore) {
      reason = "Safer route found as conditions changed";
    } else {
      reason = "Route calculated";
    }

    return {
      reason,
      road_blocked: blockedRoadName,
      risk_before: Math.round(riskBefore * 100) / 100,
      risk_after: Math.round(riskAfter * 100) / 100,
      delay_saved_s: Math.round(delaySaved),
    };
  }
}