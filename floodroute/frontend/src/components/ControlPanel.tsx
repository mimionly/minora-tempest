import { useState } from "react";
import { SelectionMode } from "../types";
import { runScenario, updateWeights } from "../lib/api";

interface Props {
  mode: SelectionMode;
  setMode: (m: SelectionMode) => void;
  startId: string | null;
  incidentId: string | null;
  floodA: string | null;
  floodB: string | null;
  onGetRoute: () => void;
  onReportFlood: (depth: number) => void;
  onDispatch: (requiresDeepWater: boolean) => void;
}

const WEIGHT_KEYS = ["rainfall", "lowElevation", "waterProximity", "historicalHotspot", "slope"] as const;

export default function ControlPanel({
  mode,
  setMode,
  startId,
  incidentId,
  floodA,
  floodB,
  onGetRoute,
  onReportFlood,
  onDispatch,
}: Props) {
  const [depth, setDepth] = useState(50);
  const [weights, setWeights] = useState<Record<string, number>>({
    rainfall: 0.35,
    lowElevation: 0.25,
    waterProximity: 0.2,
    historicalHotspot: 0.15,
    slope: 0.05,
  });
  const [requiresDeepWater, setRequiresDeepWater] = useState(false);

  const handleWeightChange = (key: string, value: number) => {
    const next = { ...weights, [key]: value };
    setWeights(next);
    updateWeights(next);
  };

  return (
    <div className="bg-[#161b22] p-4 space-y-4 text-sm">
      {/* Route picking */}
      <div>
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-1">Route</div>
        <div className="flex gap-2 flex-wrap">
          <button
            className={`px-3 py-1.5 rounded ${mode === "pick-start" ? "bg-blue-600" : "bg-gray-700"}`}
            onClick={() => setMode("pick-start")}
          >
            Click map: set start {startId && "✓"}
          </button>
          <button
            className={`px-3 py-1.5 rounded ${mode === "pick-incident" ? "bg-blue-600" : "bg-gray-700"}`}
            onClick={() => setMode("pick-incident")}
          >
            Click map: set incident {incidentId && "✓"}
          </button>
          <button className="px-3 py-1.5 rounded bg-red-600 font-semibold" onClick={onGetRoute}>
            Get Safe Route
          </button>
        </div>
      </div>

      {/* Flood injection */}
      <div>
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-1">Manual Flood Injection</div>
        <div className="flex gap-2 items-center flex-wrap">
          <button
            className={`px-3 py-1.5 rounded ${mode === "pick-flood-a" ? "bg-blue-600" : "bg-gray-700"}`}
            onClick={() => setMode("pick-flood-a")}
          >
            Pick road point A {floodA && "✓"}
          </button>
          <button
            className={`px-3 py-1.5 rounded ${mode === "pick-flood-b" ? "bg-blue-600" : "bg-gray-700"}`}
            onClick={() => setMode("pick-flood-b")}
          >
            Pick road point B {floodB && "✓"}
          </button>
          <input
            type="range"
            min={0}
            max={100}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
          />
          <span>{depth}cm</span>
          <button className="px-3 py-1.5 rounded bg-orange-600 font-semibold" onClick={() => onReportFlood(depth)}>
            Apply Flood
          </button>
        </div>
      </div>

      {/* Dispatch */}
      <div>
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-1">Fleet Dispatch</div>
        <div className="flex gap-2 items-center">
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={requiresDeepWater} onChange={(e) => setRequiresDeepWater(e.target.checked)} />
            Deep water rescue
          </label>
          <button className="px-3 py-1.5 rounded bg-purple-600 font-semibold" onClick={() => onDispatch(requiresDeepWater)}>
            Dispatch to Incident
          </button>
        </div>
      </div>

      {/* Scenario */}
      <div>
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-1">Scenario</div>
        <button
          className="px-3 py-1.5 rounded bg-gray-700"
          onClick={() => runScenario("scenarios/cyclone_demo.json")}
        >
          Run Cyclone Demo Scenario
        </button>
      </div>

      {/* Risk weight sliders */}
      <div>
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-1">Risk Weights</div>
        <div className="grid grid-cols-2 gap-2">
          {WEIGHT_KEYS.map((key) => (
            <label key={key} className="flex flex-col text-xs">
              {key}: {weights[key].toFixed(2)}
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={weights[key]}
                onChange={(e) => handleWeightChange(key, Number(e.target.value))}
              />
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}