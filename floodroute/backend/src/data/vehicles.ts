import { Vehicle } from "../graph/types";
import { CONFIG } from "../config";

/** Hardcoded fleet with real-ish starting positions — fill in real node IDs from your generated graph. */
export function createInitialFleet(): Vehicle[] {
  return [
    { id: "amb-1", type: "ambulance", clearance_cm: CONFIG.VEHICLE_CLEARANCE_CM.ambulance, position_node: "REPLACE_WITH_NODE_ID", status: "available" },
    { id: "amb-2", type: "ambulance", clearance_cm: CONFIG.VEHICLE_CLEARANCE_CM.ambulance, position_node: "REPLACE_WITH_NODE_ID", status: "available" },
    { id: "truck-1", type: "truck", clearance_cm: CONFIG.VEHICLE_CLEARANCE_CM.truck, position_node: "REPLACE_WITH_NODE_ID", status: "available" },
    { id: "truck-2", type: "truck", clearance_cm: CONFIG.VEHICLE_CLEARANCE_CM.truck, position_node: "REPLACE_WITH_NODE_ID", status: "available" },
    { id: "boat-1", type: "boat", clearance_cm: CONFIG.VEHICLE_CLEARANCE_CM.boat, position_node: "REPLACE_WITH_NODE_ID", status: "available" },
  ];
}