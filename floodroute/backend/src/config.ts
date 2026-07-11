import dotenv from "dotenv";
dotenv.config();

export const CONFIG = {
  PORT: Number(process.env.PORT) || 4000,
  USE_AI: process.env.USE_AI === "true",
  GRAPH_PATH: process.env.GRAPH_PATH || "../data/region_graph.json",

  WEATHER: {
    lat: Number(process.env.WEATHER_LAT) || 12.8756,
    lon: Number(process.env.WEATHER_LON) || 74.8420,
    pollIntervalMs: 5 * 60 * 1000, // refresh every 5 min
  },

  // Risk score weights (Section 8.1) — live-adjustable via /api/config/weights
  RISK_WEIGHTS: {
    rainfall: 0.35,
    lowElevation: 0.25,
    waterProximity: 0.20,
    historicalHotspot: 0.15,
    slope: 0.05,
  },

  RISK_WEIGHT_IN_COST: 50, // multiplier: how much risk_score affects edge_cost (seconds-equivalent)
  DEPTH_PENALTY_WEIGHT: 120, // multiplier for partial depth penalty (seconds-equivalent)
  DEPTH_DECAY_CM_PER_SEC: 0.05, // ~3cm/min recession, tune for demo pacing

  VEHICLE_CLEARANCE_CM: {
    ambulance: 20,
    truck: 45,
    boat: 0, // boats deploy above 30cm threshold instead of using clearance-block logic
  },

  // Hand-flagged known-problem roads for your region (Section 8.1) —
  // fill in real road names/IDs once you've generated your graph.
  HISTORICAL_HOTSPOTS: new Set<string>([
    // "way/123456",
  ]),

  MAX_RAINFALL_MM_PER_HR: 50, // normalization ceiling for rainfall_intensity_norm
};