import { Polyline } from "react-leaflet";
import { GraphEdge, GraphNode } from "../types";
import { roadColor, roadWeight } from "../lib/colorScale";

interface Props {
  edges: GraphEdge[];
  nodesById: Map<string, GraphNode>;
}

export default function RoadLayer({ edges, nodesById }: Props) {
  return (
    <>
      {edges.map((edge) => {
        const from = nodesById.get(edge.from);
        const to = nodesById.get(edge.to);
        if (!from || !to) return null;
        return (
          <Polyline
            key={`${edge.from}|${edge.to}`}
            positions={[
              [from.lat, from.lon],
              [to.lat, to.lon],
            ]}
            pathOptions={{ color: roadColor(edge), weight: roadWeight(edge), opacity: 0.55 }}
          />
        );
      })}
    </>
  );
}