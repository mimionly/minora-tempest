interface WeatherSnapshot {
  rainfall_mm_per_hr: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  wind_speed_kph: number | null;
  river_discharge_m3s: number | null;
  observed_at: string;
  source: "live" | "fallback";
}

interface Props {
  weather: WeatherSnapshot | null;
}

export default function WeatherPanel({ weather }: Props) {
  if (!weather) return null;

  return (
    <div className="bg-[#161b22] p-4 text-sm space-y-1">
      <div className="text-xs uppercase tracking-wide text-gray-400 flex justify-between">
        <span>Live Weather</span>
        <span className={weather.source === "live" ? "text-green-400" : "text-yellow-400"}>
          {weather.source === "live" ? "● LIVE" : "● FALLBACK"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4">
        <div>Rainfall: {weather.rainfall_mm_per_hr} mm/hr</div>
        <div>Temp: {weather.temperature_c ?? "—"}°C</div>
        <div>Humidity: {weather.humidity_pct ?? "—"}%</div>
        <div>Wind: {weather.wind_speed_kph ?? "—"} km/h</div>
        {weather.river_discharge_m3s !== null && (
          <div className="col-span-2">River discharge: {weather.river_discharge_m3s} m³/s</div>
        )}
      </div>
      <div className="text-xs text-gray-500">Observed: {new Date(weather.observed_at).toLocaleTimeString()}</div>
    </div>
  );
}