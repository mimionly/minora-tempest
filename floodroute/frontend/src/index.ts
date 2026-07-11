import express from "express";
import cors from "cors";
import http from "http";
import { CONFIG } from "./config";
import { GraphStore } from "./graph/GraphStore";
import { RiskEngine } from "./engines/RiskEngine";
import { FloodEngine } from "./engines/FloodEngine";
import { RoutingEngine } from "./engines/RoutingEngine";
import { DecisionEngine } from "./engines/DecisionEngine";
import { DispatchEngine } from "./engines/DispatchEngine";
import { fetchFullWeatherSnapshot, WeatherSnapshot } from "./data/weatherClient";
import { createInitialFleet } from "./data/vehicles";
import { buildRoutes } from "./api/routes";
import { attachSocket } from "./api/socket";
import { logger } from "./utils/logger";

async function main() {
  const app = express();
  app.use(cors());
  app.use(express.json());

  const httpServer = http.createServer(app);
  const io = attachSocket(httpServer);

  // ---- Load graph (zero-pipeline: one load, all in memory from here on) ----
  const store = new GraphStore();
  store.load(CONFIG.GRAPH_PATH);

  const riskEngine = new RiskEngine(store);
  const routingEngine = new RoutingEngine(store);
  const decisionEngine = new DecisionEngine();
  const dispatchEngine = new DispatchEngine(routingEngine);
  const fleet = createInitialFleet();

  const floodEngine = new FloodEngine(store, (changedKeys) => {
    const changedEdges = changedKeys
      .map((key) => {
        const [from, to] = key.split("|");
        return store.getEdge(from, to);
      })
      .filter(Boolean);
    io.emit("graph:update", { changedEdges });
  });

  // ---- Shared live weather state, exposed via GET /api/weather and pushed via socket ----
  let latestWeather: WeatherSnapshot;

  const refreshWeather = async () => {
    latestWeather = await fetchFullWeatherSnapshot();
    riskEngine.recomputeAll({ rainfall_mm_per_hr: latestWeather.rainfall_mm_per_hr });
    io.emit("graph:update", { changedEdges: store.snapshotEdges() });
    io.emit("weather:update", latestWeather);
    logger.info(
      `Weather refreshed: ${latestWeather.rainfall_mm_per_hr}mm/hr, ${latestWeather.temperature_c}°C ` +
        `(${latestWeather.source}, observed ${latestWeather.observed_at})`
    );
  };

  // ---- Initial fetch before the server starts accepting requests ----
  await refreshWeather();

  // ---- Background refresh — network calls NEVER happen during a route request ----
  setInterval(refreshWeather, CONFIG.WEATHER.pollIntervalMs);

  // ---- Flood depth decay tick ----
  setInterval(() => {
    floodEngine.tick();
  }, 3000);

  // ---- Routes ----
  app.use(
    "/api",
    buildRoutes(
      store,
      riskEngine,
      floodEngine,
      routingEngine,
      decisionEngine,
      dispatchEngine,
      fleet,
      io,
      () => latestWeather
    )
  );

  httpServer.listen(CONFIG.PORT, () => {
    logger.info(`FloodRoute backend running on http://localhost:${CONFIG.PORT}`);
  });
}

main().catch((e) => {
  console.error("FATAL:", e);
  process.exit(1);
});