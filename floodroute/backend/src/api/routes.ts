import { Router, Request, Response } from "express";
import fs from "fs";
import path from "path";
import { GraphStore } from "../graph/GraphStore";
import { RiskEngine } from "../engines/RiskEngine";
import { FloodEngine } from "../engines/FloodEngine";
import { RoutingEngine } from "../engines/RoutingEngine";
import { DecisionEngine } from "../engines/DecisionEngine";
import { DispatchEngine } from "../engines/DispatchEngine";
import { Vehicle, RouteResult } from "../graph/types";
import { CONFIG } from "../config";
import { Server as SocketServer } from "socket.io";

export function buildRoutes(
  store: GraphStore,
  riskEngine: RiskEngine,
  floodEngine: FloodEngine,
  routingEngine: RoutingEngine,
  decisionEngine: DecisionEngine,
  dispatchEngine: DispatchEngine,
  fleet: Vehicle[],
  io: SocketServer
) {
  const router = Router();
  let lastRouteByVehicle = new Map<string, RouteResult>();

  router.get("/health", (_req, res) => res.json({ status: "ok" }));

  router.get("/graph", (_req, res) => {
    res.json({
      nodes: Array.from(store.nodes.values()),
      edges: store.snapshotEdges(),
    });
  });

  router.post("/route", (req: Request, res: Response) => {
    const { from, to, vehicleType = "ambulance" } = req.body;
    const clearance = CONFIG.VEHICLE_CLEARANCE_CM[vehicleType as keyof typeof CONFIG.VEHICLE_CLEARANCE_CM] ?? 20;
    const result = routingEngine.findRoute(from, to, clearance);

    if (result.error) {
      return res.status(400).json(result);
    }
    res.json(result);
  });

  router.post("/flood/event", (req: Request, res: Response) => {
    const { from, to, depth_cm } = req.body;
    try {
      floodEngine.applyEvent(from, to, depth_cm);
      const edge = store.getEdge(from, to);
      io.emit("graph:update", { changedEdges: [edge] });
      io.emit("decision:update", decisionEngine.explain(null, routingEngine.findRoute(from, to, 45), edge?.name ?? null));
      res.json({ ok: true, edge });
    } catch (e: any) {
      res.status(400).json({ error: e.message });
    }
  });

  router.post("/scenario/run", (req: Request, res: Response) => {
    const { scenarioPath } = req.body;
    const fullPath = path.resolve(__dirname, "../../../", scenarioPath);
    const scenario = JSON.parse(fs.readFileSync(fullPath, "utf-8"));

    scenario.events.forEach((ev: any) => {
      setTimeout(() => {
        const [from, to] = ev.roadId.split("|");
        try {
          floodEngine.applyEvent(from, to, ev.depth_cm);
          const edge = store.getEdge(from, to);
          io.emit("graph:update", { changedEdges: [edge] });
        } catch (e) {
          console.warn("Scenario event failed:", ev, e);
        }
      }, ev.timestamp_offset_s * 1000);
    });

    res.json({ ok: true, eventsScheduled: scenario.events.length });
  });

  router.post("/dispatch", (req: Request, res: Response) => {
    const { incidentNodeId, requiresDeepWater = false } = req.body;
    const result = dispatchEngine.dispatch(fleet, incidentNodeId, requiresDeepWater);

    if (!result) {
      return res.status(404).json({ error: "No suitable vehicle available" });
    }

    result.vehicle.status = "assigned";
    result.vehicle.assigned_incident = incidentNodeId;
    lastRouteByVehicle.set(result.vehicle.id, result.route);

    io.emit("vehicle:update", { vehicle: result.vehicle, route: result.route, score: result.score });
    res.json(result);
  });

  router.get("/vehicles", (_req, res) => res.json(fleet));

  router.post("/config/weights", (req: Request, res: Response) => {
    riskEngine.setWeights(req.body);
    res.json({ ok: true, weights: riskEngine.getWeights() });
  });

  return router;
}