import { useEffect, useState, useCallback } from "react";
import MapView from "./components/MapView";
import ControlPanel from "./components/ControlPanel";
import StatusPanel from "./components/StatusPanel";
import FleetPanel from "./components/FleetPanel";
import WeatherPanel from "./components/WeatherPanel";
import { useGraphState } from "./hooks/useGraphState";
import { useSocket } from "./hooks/useSocket";
import { fetchGraph, fetchVehicles, requestRoute, reportFlood, dispatchVehicle, fetchWeather } from "./lib/api";
import { RouteResult, DecisionExplanation, Vehicle, SelectionMode, GraphEdge } from "./types";

export default function App() {
  const { nodes, edges, nodesById, floodedEdges, loadInitial, applyEdgeUpdates } = useGraphState();
  const socketRef = useSocket();

  const [weather, setWeather] = useState<any>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [decision, setDecision] = useState<DecisionExplanation | null>(null);

  const [mode, setMode] = useState<SelectionMode>("idle");
  const [startId, setStartId] = useState<string | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [floodA, setFloodA] = useState<string | null>(null);
  const [floodB, setFloodB] = useState<string | null>(null);

  // ---- Initial data load ----
  useEffect(() => {
    fetchGraph().then(({ nodes, edges }) => loadInitial(nodes, edges));
    fetchVehicles().then(setVehicles);
    fetchWeather().then(setWeather);
  }, [loadInitial]);

  // ---- Live socket listeners ----
  useEffect(() => {
    const socket = socketRef.current;
    if (!socket) return;

    socket.on("graph:update", (payload: { changedEdges: GraphEdge[] }) => {
      applyEdgeUpdates(payload.changedEdges);
    });

    socket.on("decision:update", (payload: DecisionExplanation) => {
      setDecision(payload);
    });

    socket.on("vehicle:update", (payload: { vehicle: Vehicle }) => {
      setVehicles((prev) => prev.map((v) => (v.id === payload.vehicle.id ? payload.vehicle : v)));
    });

    socket.on("weather:update", (payload) => {
      setWeather(payload);
    });

    return () => {
      socket.off("graph:update");
      socket.off("decision:update");
      socket.off("vehicle:update");
      socket.off("weather:update");
    };
  }, [socketRef, applyEdgeUpdates]);

  const handleNodePicked = useCallback(
    (nodeId: string) => {
      if (mode === "pick-start") setStartId(nodeId);
      if (mode === "pick-incident") setIncidentId(nodeId);
      if (mode === "pick-flood-a") setFloodA(nodeId);
      if (mode === "pick-flood-b") setFloodB(nodeId);
      setMode("idle");
    },
    [mode]
  );

  const handleGetRoute = async () => {
    if (!startId || !incidentId) return;
    const result = await requestRoute(startId, incidentId);
    setRoute(result);
  };

  const handleReportFlood = async (depth: number) => {
    if (!floodA || !floodB) return;
    try {
      await reportFlood(floodA, floodB, depth);
    } catch (e: any) {
      alert(e?.response?.data?.error || "Flood report failed — are those two points connected by a real road?");
    }
  };

  const handleDispatch = async (requiresDeepWater: boolean) => {
    if (!incidentId) {
      alert("Pick an incident location first.");
      return;
    }
    try {
      const result = await dispatchVehicle(incidentId, requiresDeepWater);
      setRoute(result.route);
      fetchVehicles().then(setVehicles);
    } catch (e: any) {
      alert(e?.response?.data?.error || "Dispatch failed — no suitable vehicle available.");
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-[#161b22] border-b-2 border-red-500 px-6 py-3">
        <h1 className="text-lg font-bold text-red-500">🌊 FloodRoute — Live Evacuation Routing</h1>
        <p className="text-xs text-gray-400">Zero-pipeline · Sub-second A* · No commercial map API</p>
      </header>

      <div className="flex-1 flex min-h-0">
        <div className="flex-1">
          <MapView
            nodes={nodes}
            edges={edges}
            nodesById={nodesById}
            floodedEdges={floodedEdges}
            route={route}
            vehicles={vehicles}
            mode={mode}
            onNodePicked={handleNodePicked}
          />
        </div>

        <div className="w-96 overflow-y-auto flex flex-col divide-y divide-gray-800">
          <WeatherPanel weather={weather} />
          <ControlPanel
            mode={mode}
            setMode={setMode}
            startId={startId}
            incidentId={incidentId}
            floodA={floodA}
            floodB={floodB}
            onGetRoute={handleGetRoute}
            onReportFlood={handleReportFlood}
            onDispatch={handleDispatch}
          />
          <StatusPanel route={route} decision={decision} />
          <FleetPanel vehicles={vehicles} />
        </div>
      </div>
    </div>
  );
}