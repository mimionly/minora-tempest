import { Vehicle } from "../types";

interface Props {
  vehicles: Vehicle[];
}

export default function FleetPanel({ vehicles }: Props) {
  return (
    <div className="bg-[#161b22] p-4 text-sm">
      <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">Fleet</div>
      <div className="space-y-1">
        {vehicles.map((v) => (
          <div key={v.id} className="flex justify-between">
            <span>{v.id} ({v.type})</span>
            <span className={v.status === "available" ? "text-green-400" : "text-yellow-400"}>{v.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}