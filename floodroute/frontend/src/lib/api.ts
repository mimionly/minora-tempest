import axios from "axios";
import { GraphNode, GraphEdge, RouteResult, Vehicle } from "../types";

const API = axios.create({ baseURL: "http://localhost:4000/api" });

export async function fetchGraph(): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const res = await API.get("/graph");
  return res.data;
}

export async function requestRoute(from: string, to: string, vehicleType = "ambulance"): Promise<RouteResult> {
  const res = await API.post("/route", { from, to, vehicleType });
  return res.data;
}

export async function reportFlood(from: string, to: string, depth_cm: number) {
  const res = await API.post("/flood/event", { from, to, depth_cm });
  return res.data;
}

export async function runScenario(scenarioPath: string) {
  const res = await API.post("/scenario/run", { scenarioPath });
  return res.data;
}

export async function fetchVehicles(): Promise<Vehicle[]> {
  const res = await API.get("/vehicles");
  return res.data;
}

export async function dispatchVehicle(incidentNodeId: string, requiresDeepWater = false) {
  const res = await API.post("/dispatch", { incidentNodeId, requiresDeepWater });
  return res.data;
}

export async function updateWeights(weights: Record<string, number>) {
  const res = await API.post("/config/weights", weights);
  return res.data;
}

export async function fetchWeather() {
  const res = await API.get("/weather");
  return res.data;
}