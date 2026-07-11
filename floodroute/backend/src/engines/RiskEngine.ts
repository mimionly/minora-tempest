import { GraphStore } from "../graph/GraphStore";
import { CONFIG } from "../config";
import { logger } from "../utils/logger";

interface WeatherSnapshot {
  rainfall_mm_per_hr: number;
}

/**
 * Predictive risk layer (Section 8.1). Runs BEFORE any flood is observed —
 * this is what makes routing proactive rather than purely reactive.
 * Pure function of terrain + weather; no network calls happen inside this
 * engine itself, keeping route computation latency untouched by it.
 */
export class RiskEngine {
  private weights = { ...CONFIG.RISK_WEIGHTS };
  private regionMaxElevation = 1; // updated once from graph data on init

  constructor(private store: GraphStore) {
    let max = 0;
    for (const n of store.nodes.values()) {
      if (n.elevation_m > max) max = n.elevation_m;
    }
    this.regionMaxElevation = Math.max(max, 1);
  }

  setWeights(partial: Partial<typeof this.weights>) {
    this.weights = { ...this.weights, ...partial };
    logger.info("Risk weights updated:", this.weights);
  }

  getWeights() {
    return { ...this.weights };
  }

  /** Recomputes risk_score for every edge based on current weather. Cheap — pure arithmetic over the graph already in memory. */
  recomputeAll(weather: WeatherSnapshot) {
    const rainfallNorm = Math.min(weather.rainfall_mm_per_hr / CONFIG.MAX_RAINFALL_MM_PER_HR, 1);

    for (const edge of this.store.snapshotEdges()) {
      const fromNode = this.store.nodes.get(edge.from);
      const toNode = this.store.nodes.get(edge.to);
      if (!fromNode || !toNode) continue;

      const avgElevation = (fromNode.elevation_m + toNode.elevation_m) / 2;
      const lowElevationFactor = 1 - Math.min(avgElevation / this.regionMaxElevation, 1);

      // Simple proxy: closer to sea level (elevation near 0) also implies
      // closer to coast/waterway for a coastal region like this.
      const waterProximityFactor = avgElevation < 5 ? 1 - avgElevation / 5 : 0;

      const roadKey = `${edge.from}|${edge.to}`;
      const hotspotFactor = CONFIG.HISTORICAL_HOTSPOTS.has(roadKey) ? 1 : 0;

      const slopeFactor = Math.min(Math.abs(fromNode.elevation_m - toNode.elevation_m) / 10, 1);

      const risk =
        rainfallNorm * this.weights.rainfall +
        lowElevationFactor * this.weights.lowElevation +
        waterProximityFactor * this.weights.waterProximity +
        hotspotFactor * this.weights.historicalHotspot +
        slopeFactor * this.weights.slope;

      edge.risk_score = Math.min(Math.max(risk, 0), 1);
    }
  }
}