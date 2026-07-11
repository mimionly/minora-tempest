import { Circle } from "react-leaflet";
import { GraphEdge, GraphNode } from "../types";
import { floodColor, floodRadiusM } from "../lib/colorScale";

interface Props {
  floodedEdges: GraphEdge[];
  nodesById: Map<string, GraphNode>;
}

export default function FloodZoneLayer({ floodedEdges, nodesById }: Props) {
  return (
    <>
      {floodedEdges.map((edge) => {
        const from = nodesById.get(edge.from);
        const to = nodesById.get(edge.to);
        if (!from || !to) return null;
        const midLat = (from.lat + to.lat) / 2;
        const midLon = (from.lon + to.lon) / 2;
        return (
          <Circle
            key={`flood-${edge.from}|${edge.to}`}
            center={[midLat, midLon]}
            radius={floodRadiusM(edge.depth_cm)}
            pathOptions={{ color: "transparent", fillColor: floodColor(edge.depth_cm), fillOpacity: 1 }}
          />
        );
      })}
    </>
  );
}