import fs from "fs";
import path from "path";
import { GraphNode, GraphEdge } from "./types";
import { logger } from "../utils/logger";

/**
 * In-memory graph store. Matches the zero-pipeline constraint exactly:
 * loaded once from the static export file, then mutated directly in
 * memory by RiskEngine/FloodEngine — no DB, no batch sync, ever.
 */
export class GraphStore {
  nodes = new Map<string, GraphNode>();
  // adjacency: nodeId -> array of edges touching it (both directions)
  adjacency = new Map<string, GraphEdge[]>();
  // fast lookup for a specific edge by "from|to" (order-independent)
  edgeIndex = new Map<string, GraphEdge>();

  load(graphPath: string) {
    const fullPath = path.resolve(process.cwd(), graphPath);
    const raw = fs.readFileSync(fullPath, "utf-8");
    const data = JSON.parse(raw);

    for (const n of data.nodes as GraphNode[]) {
      this.nodes.set(n.id, n);
      this.adjacency.set(n.id, []);
    }

    for (const e of data.edges) {
      const edge: GraphEdge = {
        ...e,
        risk_score: 0,
        depth_cm: 0,
        blocked: false,
      };
      this.addEdgeBothDirections(edge);
    }

    logger.info(`GraphStore loaded: ${this.nodes.size} nodes, ${this.edgeIndex.size} unique roads`);
  }

  private edgeKey(a: string, b: string): string {
    return [a, b].sort().join("|");
  }

  private addEdgeBothDirections(edge: GraphEdge) {
    const key = this.edgeKey(edge.from, edge.to);
    this.edgeIndex.set(key, edge);
    this.adjacency.get(edge.from)?.push(edge);
    // undirected: also reachable from 'to' back to 'from'
    this.adjacency.get(edge.to)?.push({ ...edge, from: edge.to, to: edge.from });
  }

  getEdge(a: string, b: string): GraphEdge | undefined {
    return this.edgeIndex.get(this.edgeKey(a, b));
  }

  neighbors(nodeId: string): GraphEdge[] {
    return this.adjacency.get(nodeId) || [];
  }

  /** Current traversal cost for an edge: travel time + risk penalty + depth penalty. */
  edgeCost(edge: GraphEdge, riskWeightInCost: number, depthPenaltyWeight: number, clearanceCm: number): number {
    if (edge.depth_cm > clearanceCm) return Infinity;
    const depthPenalty = clearanceCm > 0 ? (edge.depth_cm / clearanceCm) * depthPenaltyWeight : 0;
    return edge.travel_time_s + edge.risk_score * riskWeightInCost + depthPenalty;
  }

  snapshotEdges() {
    return Array.from(this.edgeIndex.values());
  }
}