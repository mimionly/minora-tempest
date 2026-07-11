import { RouteResult, DecisionExplanation } from "../types";

interface Props {
  route: RouteResult | null;
  decision: DecisionExplanation | null;
}

export default function StatusPanel({ route, decision }: Props) {
  return (
    <div className="bg-[#161b22] p-4 text-sm space-y-2">
      <div className="text-xs uppercase tracking-wide text-gray-400">Live Status</div>

      {route?.error && <div className="text-red-400">❌ {route.error}</div>}

      {route && !route.error && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <div>Calc latency: <span className="text-blue-400">{route.calc_time_ms} ms</span></div>
          <div>Nodes explored: {route.nodes_explored}</div>
          <div>Distance: {(route.total_distance_m / 1000).toFixed(2)} km</div>
          <div>ETA: {(route.estimated_time_s / 60).toFixed(1)} min</div>
          <div>Avg risk: {route.avg_risk_score}</div>
        </div>
      )}

      {decision && (
        <div className="mt-2 border-t border-gray-700 pt-2">
          <div className="text-gray-300">{decision.reason}</div>
          {decision.road_blocked && <div className="text-red-400">Blocked: {decision.road_blocked}</div>}
          <div className="text-xs text-gray-500">
            Risk {decision.risk_before} → {decision.risk_after} | Delay saved: {decision.delay_saved_s}s
          </div>
        </div>
      )}
    </div>
  );
}