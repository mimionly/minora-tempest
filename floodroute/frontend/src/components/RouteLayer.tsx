import { Polyline } from "react-leaflet";
import { RouteResult } from "../types";

interface Props {
  route: RouteResult | null;
}

export default function RouteLayer({ route }: Props) {
  if (!route || route.error || route.path_coords.length === 0) return null;
  return <Polyline positions={route.path_coords} pathOptions={{ color: "#3fb950", weight: 5, opacity: 0.95 }} />;
}