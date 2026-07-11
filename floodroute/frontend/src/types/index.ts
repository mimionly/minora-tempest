export interface GraphNode {
  id: string;
  lat: number;
  lon: number;
  elevation_m: number;
  type: "intersection" | "hospital" | "shelter" | "fire_station";
  name: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  length_m: number;
  base_speed_kph: number;
  travel_time_s: number;
  highway: string;
  name: string;
  risk_score: number;
  depth_cm: number;
  blocked: boolean;
}

export interface RouteResult {
  path_nodes: string[];
  path_coords: [number, number][];
  total_distance_m: number;
  total_cost: number;
  estimated_time_s: number;
  avg_risk_score: number;
  calc_time_ms: number;
  nodes_explored: number;
  error?: string;
}

export interface DecisionExplanation {
  reason: string;
  road_blocked: string | null;
  risk_before: number;
  risk_after: number;
  delay_saved_s: number;
}

export interface Vehicle {
  id: string;
  type: "ambulance" | "truck" | "boat";
  clearance_cm: number;
  position_node: string;
  status: "available" | "assigned" | "en_route";
  assigned_incident?: string;
}

export type SelectionMode = "idle" | "pick-start" | "pick-incident" | "pick-flood-a" | "pick-flood-b";