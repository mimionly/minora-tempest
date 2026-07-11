import axios from "axios";
import { CONFIG } from "../config";
import { logger } from "../utils/logger";

interface WeatherSnapshot {
  rainfall_mm_per_hr: number;
  source: "live" | "fallback";
}

const FALLBACK_RAINFALL_MM = 8; // stated, hardcoded "realistic" value if offline

/** Open-Meteo — free, no API key. Falls back to a logged, stated value if unreachable. */
export async function fetchCurrentRainfall(): Promise<WeatherSnapshot> {
  try {
    const { lat, lon } = CONFIG.WEATHER;
    const res = await axios.get("https://api.open-meteo.com/v1/forecast", {
      params: { latitude: lat, longitude: lon, hourly: "precipitation", forecast_days: 1 },
      timeout: 5000,
    });
    const precipArray: number[] = res.data.hourly.precipitation;
    const currentHourIndex = new Date().getUTCHours();
    const rainfall = precipArray[currentHourIndex] ?? precipArray[0] ?? 0;
    return { rainfall_mm_per_hr: rainfall, source: "live" };
  } catch (e) {
    logger.warn("Weather API unreachable — using fallback rainfall value", e);
    return { rainfall_mm_per_hr: FALLBACK_RAINFALL_MM, source: "fallback" };
  }
}