import axios from "axios";
import { CONFIG } from "../config";
import { logger } from "../utils/logger";

export interface WeatherSnapshot {
  rainfall_mm_per_hr: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  wind_speed_kph: number | null;
  weather_code: number | null;
  river_discharge_m3s: number | null;
  observed_at: string; // ISO timestamp, taken directly from the API response
  source: "live" | "fallback";
}

const FALLBACK_RAINFALL_MM = 8; // stated, logged fallback if the API is unreachable

function fallbackSnapshot(): WeatherSnapshot {
  return {
    rainfall_mm_per_hr: FALLBACK_RAINFALL_MM,
    temperature_c: null,
    humidity_pct: null,
    wind_speed_kph: null,
    weather_code: null,
    river_discharge_m3s: null,
    observed_at: new Date().toISOString(),
    source: "fallback",
  };
}

/**
 * Fetches TRUE real-time conditions using Open-Meteo's `current` parameter —
 * this returns the live observation directly with its own timestamp, instead
 * of guessing which index in an hourly array corresponds to "now" (which was
 * the earlier bug: UTC-hour indexing into a possibly-local-timezone array).
 */
export async function fetchCurrentWeather(): Promise<WeatherSnapshot> {
  try {
    const { lat, lon } = CONFIG.WEATHER;
    const res = await axios.get("https://api.open-meteo.com/v1/forecast", {
      params: {
        latitude: lat,
        longitude: lon,
        current: "temperature_2m,precipitation,rain,weather_code,wind_speed_10m,relative_humidity_2m",
        timezone: "auto",
      },
      timeout: 5000,
    });

    const c = res.data?.current;
    if (!c) throw new Error("Open-Meteo response missing 'current' block");

    return {
      rainfall_mm_per_hr: c.precipitation ?? c.rain ?? 0,
      temperature_c: c.temperature_2m ?? null,
      humidity_pct: c.relative_humidity_2m ?? null,
      wind_speed_kph: c.wind_speed_10m ?? null,
      weather_code: c.weather_code ?? null,
      river_discharge_m3s: null, // filled in separately below
      observed_at: c.time ?? new Date().toISOString(),
      source: "live",
    };
  } catch (e) {
    logger.warn("Weather API unreachable — using fallback rainfall value", e);
    return fallbackSnapshot();
  }
}

/**
 * Optional secondary signal: river discharge from Open-Meteo's Global Flood
 * API (GloFAS reanalysis/forecast). ~5km resolution, so treat it as a coarse
 * regional signal, not a per-road-segment measurement.
 */
export async function fetchRiverDischarge(): Promise<number | null> {
  try {
    const { lat, lon } = CONFIG.WEATHER;
    const res = await axios.get("https://flood-api.open-meteo.com/v1/flood", {
      params: { latitude: lat, longitude: lon, daily: "river_discharge", forecast_days: 1 },
      timeout: 5000,
    });
    const val = res.data?.daily?.river_discharge?.[0];
    return typeof val === "number" ? val : null;
  } catch (e) {
    logger.warn("Flood API unreachable — river discharge unavailable this cycle", e);
    return null;
  }
}

/** Combines both calls into one snapshot used by RiskEngine and exposed via /api/weather. */
export async function fetchFullWeatherSnapshot(): Promise<WeatherSnapshot> {
  const [weather, discharge] = await Promise.all([fetchCurrentWeather(), fetchRiverDischarge()]);
  return { ...weather, river_discharge_m3s: discharge };
}