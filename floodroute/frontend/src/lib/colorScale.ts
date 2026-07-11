import { GraphEdge } from "../types";

/** Road color: green (safe) -> yellow (risky) -> red (blocked/high-risk). */
export function roadColor(edge: GraphEdge): string {
  if (edge.blocked) return "#f85149";
  if (edge.risk_score > 0.6) return "#f85149";
  if (edge.risk_score > 0.3) return "#d29922";
  return "#3fb950";
}

export function roadWeight(edge: GraphEdge): number {
  return edge.blocked || edge.risk_score > 0.6 ? 4 : 2;
}

/** Flood zone circle radius (meters) scaled by depth. */
export function floodRadiusM(depth_cm: number): number {
  return Math.min(30 + depth_cm * 1.5, 250);
}

/** Blue gradient opacity scaled by depth. */
export function floodColor(depth_cm: number): string {
  const alpha = Math.min(0.15 + depth_cm / 100, 0.75);
  return `rgba(56,139,253,${alpha})`;
}

/** Straight-line distance in km — used for client-side nearest-node lookups. */
export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}