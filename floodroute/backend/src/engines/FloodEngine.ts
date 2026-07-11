import { GraphStore } from "../graph/GraphStore";
import { FloodEvent } from "../graph/types";
import { CONFIG } from "../config";
import { logger } from "../utils/logger";

/**
 * Observed-flooding layer (Section 8.2/8.5). Applies depth events directly
 * to in-memory edges (hard block above vehicle clearance) and decays them
 * over time via a tick loop — shows the demo recovering, not just flooding.
 */
export class FloodEngine {
  private activeEvents = new Map<string, FloodEvent>(); // keyed by "from|to"

  constructor(private store: GraphStore, private onChange: (changedEdgeKeys: string[]) => void) {}

  applyEvent(fromId: string, toId: string, depthCm: number, decayRate = CONFIG.DEPTH_DECAY_CM_PER_SEC) {
    const edge = this.store.getEdge(fromId, toId);
    if (!edge) {
      throw new Error(`No road exists between ${fromId} and ${toId}`);
    }

    edge.depth_cm = depthCm;
    edge.blocked = depthCm > CONFIG.VEHICLE_CLEARANCE_CM.truck; // blocked for the toughest ground vehicle

    const key = `${fromId}|${toId}`;
    this.activeEvents.set(key, {
      roadId: key,
      depth_cm: depthCm,
      timestamp: Date.now(),
      decay_rate_cm_per_s: decayRate,
    });

    logger.info(`Flood event applied: ${edge.name} depth=${depthCm}cm blocked=${edge.blocked}`);
    this.onChange([key]);
  }

  clearEvent(fromId: string, toId: string) {
    const edge = this.store.getEdge(fromId, toId);
    if (!edge) return;
    edge.depth_cm = 0;
    edge.blocked = false;
    const key = `${fromId}|${toId}`;
    this.activeEvents.delete(key);
    this.onChange([key]);
  }

  /** Server-side tick: call every few seconds. Recedes depth, unblocks roads as they clear. */
  tick(nowMs = Date.now()) {
    const changed: string[] = [];
    for (const [key, ev] of this.activeEvents.entries()) {
      const elapsedS = (nowMs - ev.timestamp) / 1000;
      const newDepth = Math.max(0, ev.depth_cm - ev.decay_rate_cm_per_s * elapsedS);

      const [from, to] = key.split("|");
      const edge = this.store.getEdge(from, to);
      if (!edge) continue;

      edge.depth_cm = newDepth;
      edge.blocked = newDepth > CONFIG.VEHICLE_CLEARANCE_CM.truck;
      changed.push(key);

      if (newDepth <= 0) {
        this.activeEvents.delete(key);
      }
    }
    if (changed.length > 0) this.onChange(changed);
    return changed;
  }

  activeEventCount() {
    return this.activeEvents.size;
  }
}