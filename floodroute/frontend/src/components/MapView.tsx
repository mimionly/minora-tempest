import { MapContainer, TileLayer, useMapEvents, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { GraphNode, GraphEdge, RouteResult, Vehicle, SelectionMode } from "../types";
import RoadLayer from "./RoadLayer";
import FloodZoneLayer from "./FloodZoneLayer";
import RouteLayer from "./RouteLayer";
import { haversineKm } from "../lib/colorScale";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  nodesById: Map<string, GraphNode>;
  floodedEdges: GraphEdge[];
  route: RouteResult | null;
  vehicles: Vehicle[];
  mode: SelectionMode;
  onNodePicked: (nodeId: string) => void;
}

function findNearestNode(nodes: GraphNode[], lat: number, lon: number): GraphNode | null {
  let best: GraphNode | null = null;
  let bestDist = Infinity;
  for (const n of nodes) {
    const d = haversineKm(lat, lon, n.lat, n.lon);
    if (d < bestDist) {
      bestDist = d;
      best = n;
    }
  }
  return best;
}

function ClickCatcher({ nodes, onNodePicked }: { nodes: GraphNode[]; onNodePicked: (id: string) => void }) {
  useMapEvents({
    click(e) {
      const nearest = findNearestNode(nodes, e.latlng.lat, e.latlng.lng);
      if (nearest) onNodePicked(nearest.id);
    },
  });
  return null;
}

export default function MapView({ nodes, edges, nodesById, floodedEdges, route, vehicles, mode, onNodePicked }: Props) {
  const center: [number, number] = nodes.length > 0 ? [nodes[0].lat, nodes[0].lon] : [12.8756, 74.8420];

  return (
    <MapContainer center={center} zoom={13} className="h-full w-full" preferCanvas>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />

      <RoadLayer edges={edges} nodesById={nodesById} />
      <FloodZoneLayer floodedEdges={floodedEdges} nodesById={nodesById} />
      <RouteLayer route={route} />

      {vehicles.map((v) => {
        const pos = nodesById.get(v.position_node);
        if (!pos) return null;
        return (
          <CircleMarker
            key={v.id}
            center={[pos.lat, pos.lon]}
            radius={8}
            pathOptions={{
              color: "#fff",
              fillColor: v.status === "available" ? "#58a6ff" : "#d29922",
              fillOpacity: 1,
              weight: 2,
            }}
          >
            <Popup>
              {v.id} ({v.type}) — {v.status}
            </Popup>
          </CircleMarker>
        );
      })}

      {mode !== "idle" && <ClickCatcher nodes={nodes} onNodePicked={onNodePicked} />}
    </MapContainer>
  );
}