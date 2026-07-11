import { GraphStore } from "../graph/GraphStore";
import { haversineKm } from "../utils/haversine";
import { RouteResult } from "../graph/types";
import { CONFIG } from "../config";

interface QueueItem {
  nodeId: string;
  fScore: number;
}

/** Simple binary-heap-free priority queue — fine at this graph scale (thousands of nodes, sub-second target). */
class MinPriorityQueue {
  private items: QueueItem[] = [];
  push(item: QueueItem) {
    this.items.push(item);
    this.items.sort((a, b) => a.fScore - b.fScore);
  }
  pop(): QueueItem | undefined {
    return this.items.shift();
  }
  get length() {
    return this.items.length;
  }
}

export class RoutingEngine {
  constructor(private store: GraphStore) {}

  /**
   * A* search, haversine-based admissible heuristic. Full re-run on every
   * call — at this graph size that's already comfortably sub-second, so no
   * incremental/partial-recompute trick is claimed or needed.
   */
  findRoute(startId: string, endId: string, vehicleClearanceCm: number): RouteResult {
    const t0 = performance.now();

    const start = this.store.nodes.get(startId);
    const end = this.store.nodes.get(endId);
    if (!start || !end) {
      return this.emptyResult(`Unknown junction(s): ${startId}, ${endId}`, t0);
    }

    const maxSpeedKph = 60; // heuristic assumes best-case speed, keeps it admissible
    const heuristic = (nodeId: string) => {
      const n = this.store.nodes.get(nodeId)!;
      const distKm = haversineKm(n.lat, n.lon, end.lat, end.lon);
      return (distKm / maxSpeedKph) * 3600; // seconds
    };

    const gScore = new Map<string, number>([[startId, 0]]);
    const cameFrom = new Map<string, string>();
    const visited = new Set<string>();
    const open = new MinPriorityQueue();
    open.push({ nodeId: startId, fScore: heuristic(startId) });

    let nodesExplored = 0;

    while (open.length > 0) {
      const current = open.pop()!;
      if (visited.has(current.nodeId)) continue;
      visited.add(current.nodeId);
      nodesExplored++;

      if (current.nodeId === endId) {
        return this.reconstructPath(cameFrom, startId, endId, gScore, t0, nodesExplored);
      }

      for (const edge of this.store.neighbors(current.nodeId)) {
        const cost = this.store.edgeCost(
          edge,
          CONFIG.RISK_WEIGHT_IN_COST,
          CONFIG.DEPTH_PENALTY_WEIGHT,
          vehicleClearanceCm
        );
        if (cost === Infinity) continue; // hard-blocked road

        const tentativeG = (gScore.get(current.nodeId) ?? Infinity) + cost;
        if (tentativeG < (gScore.get(edge.to) ?? Infinity)) {
          gScore.set(edge.to, tentativeG);
          cameFrom.set(edge.to, current.nodeId);
          open.push({ nodeId: edge.to, fScore: tentativeG + heuristic(edge.to) });
        }
      }
    }

    return this.emptyResult("No safe route available — area is cut off by flooding.", t0, nodesExplored);
  }

  private reconstructPath(
    cameFrom: Map<string, string>,
    startId: string,
    endId: string,
    gScore: Map<string, number>,
    t0: number,
    nodesExplored: number
  ): RouteResult {
    const path: string[] = [endId];
    let current = endId;
    while (current !== startId) {
      const prev = cameFrom.get(current);
      if (!prev) break;
      path.unshift(prev);
      current = prev;
    }

    let totalDistanceM = 0;
    let totalRisk = 0;
    let riskSamples = 0;
    const coords: [number, number][] = [];

    for (let i = 0; i < path.length; i++) {
      const node = this.store.nodes.get(path[i])!;
      coords.push([node.lat, node.lon]);
      if (i < path.length - 1) {
        const edge = this.store.getEdge(path[i], path[i + 1]);
        if (edge) {
          totalDistanceM += edge.length_m;
          totalRisk += edge.risk_score;
          riskSamples++;
        }
      }
    }

    return {
      path_nodes: path,
      path_coords: coords,
      total_distance_m: Math.round(totalDistanceM),
      total_cost: Math.round((gScore.get(endId) ?? 0) * 100) / 100,
      estimated_time_s: Math.round(gScore.get(endId) ?? 0),
      avg_risk_score: riskSamples > 0 ? Math.round((totalRisk / riskSamples) * 100) / 100 : 0,
      calc_time_ms: Math.round((performance.now() - t0) * 100) / 100,
      nodes_explored: nodesExplored,
    };
  }

  private emptyResult(error: string, t0: number, nodesExplored = 0): RouteResult {
    return {
      path_nodes: [],
      path_coords: [],
      total_distance_m: 0,
      total_cost: 0,
      estimated_time_s: 0,
      avg_risk_score: 0,
      calc_time_ms: Math.round((performance.now() - t0) * 100) / 100,
      nodes_explored: nodesExplored,
      error,
    };
  }
}