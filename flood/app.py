import os
import pickle
import time
import traceback
import requests
import joblib
import networkx as nx
import osmnx as ox
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

ox.settings.use_cache = True
ox.settings.log_console = False

CITY_COORDINATES = {
    "Mangaluru": {"lat": 12.8701, "lon": 74.8800, "radius": 4000},
    "Patna": {"lat": 25.5941, "lon": 85.1376, "radius": 4000}
}

# Critical hydrological boundaries for localized elevation risk distribution
MANGALURU_RIVERS = [
    {"name": "Netravati Southern Basin", "lat": 12.8480, "lon": 74.8450, "vulnerability": 1.6},
    {"name": "Gurupura Northern Outlet", "lat": 12.8920, "lon": 74.8280, "vulnerability": 1.4}
]

PATNA_RIVERS = [
    {"name": "Ganga River Bank (West)", "lat": 25.630, "lon": 85.100},
    {"name": "Ganga River Bank (Center)", "lat": 25.630, "lon": 85.137},
    {"name": "Ganga River Bank (East)", "lat": 25.630, "lon": 85.175},
]

class CoastalFloodRouter:
    def __init__(self):
        try:
            self.reg = joblib.load("flood_risk_regressor.joblib")
            print("Successfully loaded calibrated flood risk ML Regressor.")
        except FileNotFoundError:
            print("ML model binaries not found. Using optimized mathematical defaults.")
            self.reg = None

        self.graph = None
        self.current_location = ""
        self.baseline_features = {
            "Parmanent_Water": 2.8,
            "fatality_rate": 6.77,
            "injury_rate": 1.93,
            "Population": 620000
        }
        # Weather cache: { (lat_rounded, lon_rounded): (timestamp, result) }
        self._weather_cache = {}
        self._weather_ttl = 60  # seconds
        # Pre-computed per-node proximity factor (rebuilt on city change)
        self._node_prox_factor = {}

    def load_network_if_new(self, key_name):
        if self.current_location == key_name and self.graph is not None:
            return

        cache_dir = "cache"
        os.makedirs(cache_dir, exist_ok=True)
        pickle_path = os.path.join(cache_dir, f"{key_name}_network.pickle")

        if os.path.exists(pickle_path):
            print(f"Loading {key_name} topology from pre-compiled binary cache...")
            t0 = time.time()
            with open(pickle_path, 'rb') as f:
                self.graph = pickle.load(f)
            print(f"  -> Loaded in {(time.time()-t0)*1000:.0f}ms")
        else:
            print(f"No binary cache found. Fetching {key_name} topology from OpenStreetMap...")
            config = CITY_COORDINATES[key_name]
            self.graph = ox.graph_from_point(
                (config["lat"], config["lon"]),
                dist=config["radius"],
                network_type="drive"
            )
            with open(pickle_path, 'wb') as f:
                pickle.dump(self.graph, f, pickle.HIGHEST_PROTOCOL)
            print(f"Successfully serialized and cached {key_name} topology.")

        self.current_location = key_name

        # Initialise edge attributes
        for u, v, k, data in self.graph.edges(data=True, keys=True):
            data['base_length'] = data.get('length', 1.0)
            data['current_weight'] = data['base_length']
            data['is_blocked'] = False

        # Pre-compute per-node proximity factors (vectorised)
        self._precompute_node_proximity()

    def _precompute_node_proximity(self):
        """Vectorised numpy computation of proximity factor per node."""
        node_ids = list(self.graph.nodes())
        nodes_arr = np.array([
            [self.graph.nodes[n].get('y', 0.0), self.graph.nodes[n].get('x', 0.0)]
            for n in node_ids
        ])
        if self.current_location == "Mangaluru":
            river_arr = np.array([[r["lat"], r["lon"]] for r in MANGALURU_RIVERS])
            # shape: (N, R)
            dists = np.sqrt(
                ((nodes_arr[:, None, :] - river_arr[None, :, :]) ** 2).sum(axis=2)
            ).min(axis=1)
            prox = np.where(dists < 0.015, 1.4 * (1.0 - (dists / 0.015)), 0.55)
        elif self.current_location == "Patna":
            river_arr = np.array([[r["lat"], r["lon"]] for r in PATNA_RIVERS])
            dists = np.sqrt(
                ((nodes_arr[:, None, :] - river_arr[None, :, :]) ** 2).sum(axis=2)
            ).min(axis=1)
            prox = np.where(dists < 0.040, 1.4 * (1.0 - (dists / 0.040)), 0.55)
        else:
            prox = np.ones(len(node_ids))
        self._node_prox_factor = {node_ids[i]: float(prox[i]) for i in range(len(node_ids))}

    def fetch_live_weather(self, lat, lon):
        # Round coords to 2 dp for cache key (~1km resolution)
        key = (round(lat, 2), round(lon, 2))
        now = time.time()
        if key in self._weather_cache:
            ts, result = self._weather_cache[key]
            if now - ts < self._weather_ttl:
                return result
        try:
            url = (f"https://api.open-meteo.com/v1/forecast"
                   f"?latitude={lat}&longitude={lon}&current_weather=true")
            response = requests.get(url, timeout=5).json()
            current = response.get("current_weather", {})
            wind = current.get("windspeed", 12.0)
            percent_flooded = min(max(15.0 + (wind % 10), 12.0), 30.0)
            result = {"Percent_Flooded_Area": percent_flooded, "Mean_Flood_Duration": 10.5}
        except Exception:
            result = {"Percent_Flooded_Area": 18.4, "Mean_Flood_Duration": 10.5}
        self._weather_cache[key] = (now, result)
        return result

    def adapt_network_weights(self, center_lat, center_lon, custom_block_text=""):
        weather = self.fetch_live_weather(center_lat, center_lon)
        payload = pd.DataFrame([{
            "Percent_Flooded_Area": weather["Percent_Flooded_Area"],
            "Parmanent_Water": self.baseline_features["Parmanent_Water"],
            "Corrected_Percent_Flooded_Area": (
                weather["Percent_Flooded_Area"] - self.baseline_features["Parmanent_Water"]
            ),
            "fatality_rate": self.baseline_features["fatality_rate"],
            "injury_rate": self.baseline_features["injury_rate"],
            "Mean_Flood_Duration": weather["Mean_Flood_Duration"],
            "Population": self.baseline_features["Population"]
        }])

        if self.reg:
            district_base_score = float(self.reg.predict(payload)[0])
        else:
            district_base_score = 52.4

        if district_base_score >= 60.0:   risk_tier = "Very High"
        elif district_base_score >= 45.0: risk_tier = "High"
        elif district_base_score >= 25.0: risk_tier = "Medium"
        else:                              risk_tier = "Low"

        block_keyword = custom_block_text.strip().lower()
        submerged_edges = []
        warn_edges = []
        
        green_nodes = set()
        fallback_nodes = set()

        for u, v, k, data in self.graph.edges(data=True, keys=True):
            # Use pre-computed proximity factor (average of both ends for symmetry)
            prox_u = self._node_prox_factor.get(u, 1.0)
            prox_v = self._node_prox_factor.get(v, 1.0)
            proximity_factor = (prox_u + prox_v) / 2.0
            local_road_risk = district_base_score * proximity_factor
            data['is_blocked'] = False

            # Custom manual simulator check
            edge_name = str(data.get('name', '')).lower()
            
            # Helper to extract geometry lazily only if needed
            def get_geom():
                if 'geometry' in data:
                    x_coords, y_coords = data['geometry'].xy
                    return [[y, x] for x, y in zip(x_coords, y_coords)]
                return [
                    [self.graph.nodes[u]['y'], self.graph.nodes[u]['x']],
                    [self.graph.nodes[v]['y'], self.graph.nodes[v]['x']]
                ]

            if block_keyword and (block_keyword in edge_name):
                data['is_blocked'] = True
                data['current_weight'] = float('inf')
                submerged_edges.append(get_geom())
                continue

            # Risk-tier thresholds
            if local_road_risk >= 68.0:
                data['is_blocked'] = True
                data['current_weight'] = float('inf')
                submerged_edges.append(get_geom())
            elif local_road_risk >= 42.0:
                data['current_weight'] = data['base_length'] * (1.0 + (local_road_risk * 1.5))
                warn_edges.append(get_geom())
                fallback_nodes.add(u)
                fallback_nodes.add(v)
            else:
                data['current_weight'] = data['base_length']
                green_nodes.add(u)
                green_nodes.add(v)
                fallback_nodes.add(u)
                fallback_nodes.add(v)

        return district_base_score, risk_tier, submerged_edges, warn_edges, green_nodes, fallback_nodes

    def _nearest_safe_node(self, lat, lon, active_nodes):
        """Find the nearest node (from active_nodes set) to (lat, lon).
        Only searches nodes that actually have edges in the filtered graph,
        preventing silent fallback caused by snapping to isolated nodes."""
        nodes_df = pd.DataFrame(
            [(n, self.graph.nodes[n]['y'], self.graph.nodes[n]['x'])
             for n in active_nodes],
            columns=['node', 'lat', 'lon']
        )
        nodes_df['dist'] = (
            (nodes_df['lat'] - lat) ** 2 + (nodes_df['lon'] - lon) ** 2
        )
        return int(nodes_df.loc[nodes_df['dist'].idxmin(), 'node'])

    def _build_route_coords(self, graph, path):
        """Extract detailed lat/lon coordinates along a node path."""
        detailed_coords = []
        for u, v in zip(path[:-1], path[1:]):
            edge_data = graph.get_edge_data(u, v)
            if edge_data is None:
                continue
            data = edge_data[0] if 0 in edge_data else list(edge_data.values())[0]
            if 'geometry' in data:
                x_coords, y_coords = data['geometry'].xy
                for x, y in zip(x_coords, y_coords):
                    detailed_coords.append([y, x])
            else:
                detailed_coords.append([
                    self.graph.nodes[u]['y'],
                    self.graph.nodes[u]['x']
                ])
        detailed_coords.append([
            self.graph.nodes[path[-1]]['y'],
            self.graph.nodes[path[-1]]['x']
        ])
        return detailed_coords

    def generate_safe_detailed_route(self, start_coords, end_coords, green_nodes, fallback_nodes):
        """
        Two-pass routing strategy:
          Pass 1 — Safe-only (green): excludes both red (blocked) and yellow (warn) edges.
                   Route uses only confirmed-safe roads.
          Pass 2 — Fallback (green + yellow): if no safe-only path exists, allow yellow
                   roads (still blocked red). Yellow edges carry a heavy weight penalty
                   so they are used only when no safe detour is available.
        Red (blocked) roads are ALWAYS excluded from both passes.
        """
        # --- Standard Path Check (To see what we actually avoided) ---
        avoided_submerged = 0
        avoided_warn = 0
        if fallback_nodes:
            try:
                orig_raw = self._nearest_safe_node(start_coords[0], start_coords[1], fallback_nodes)
                dest_raw = self._nearest_safe_node(end_coords[0], end_coords[1], fallback_nodes)
                std_path = nx.shortest_path(self.graph, source=orig_raw, target=dest_raw, weight='base_length')
                for u, v in zip(std_path[:-1], std_path[1:]):
                    ed = self.graph.get_edge_data(u, v)
                    if ed:
                        d = ed[0] if 0 in ed else list(ed.values())[0]
                        if d.get('is_blocked', False):
                            avoided_submerged += 1
                        elif d.get('current_weight', 1.0) != d.get('base_length', 1.0):
                            avoided_warn += 1
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass

        # --- Pass 1: green-only graph ---
        def green_only(u, v, k):
            d = self.graph.edges[u, v, k]
            return (not d.get('is_blocked', False) and
                    d.get('current_weight', 1.0) == d.get('base_length', 1.0))

        green_graph = nx.subgraph_view(self.graph, filter_edge=green_only)

        if green_nodes:
            orig = self._nearest_safe_node(start_coords[0], start_coords[1], green_nodes)
            dest = self._nearest_safe_node(end_coords[0], end_coords[1], green_nodes)
            try:
                path = nx.shortest_path(
                    green_graph, source=orig, target=dest, weight='current_weight'
                )
                print("Route found via safe-only (green) pass.")
                return self._build_route_coords(green_graph, path), "green", avoided_submerged, avoided_warn
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                print("Green-only pass: no path between snapped nodes — falling back.")

        # --- Pass 2: fallback — green + yellow (red still excluded) ---
        print("Falling back to green + yellow pass.")

        def not_blocked(u, v, k):
            return not self.graph.edges[u, v, k].get('is_blocked', False)

        fallback_graph = nx.subgraph_view(self.graph, filter_edge=not_blocked)

        if not fallback_nodes:
            return None, None, 0, 0

        orig = self._nearest_safe_node(start_coords[0], start_coords[1], fallback_nodes)
        dest = self._nearest_safe_node(end_coords[0], end_coords[1], fallback_nodes)

        try:
            path = nx.shortest_path(
                fallback_graph, source=orig, target=dest, weight='current_weight'
            )
            return self._build_route_coords(fallback_graph, path), "yellow", avoided_submerged, avoided_warn
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None, None, 0, 0

    def generate_reasoning(self, risk_tier, pass_used, avoided_submerged, avoided_warn):
        """Generates natural, concise reasoning based on live routing data."""
        if avoided_submerged == 0 and avoided_warn == 0:
            return "Standard optimal route selected. No flooded roads were in your way."

        reasoning = f"Area risk level is {risk_tier}. "
        
        if avoided_submerged > 0 or avoided_warn > 0:
            total_avoided = avoided_submerged + avoided_warn
            reasoning += f"Successfully avoided {total_avoided} flooded or vulnerable road segments that were on the standard path. "
            
        if pass_used == "green":
            reasoning += "Found a completely safe detour avoiding all risk zones."
        elif pass_used == "yellow":
            reasoning += "No completely safe detour exists. Routed through some low-risk zones to bypass the severe flooding. Please proceed carefully."
            
        return reasoning


router_engine = CoastalFloodRouter()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/route", methods=["POST"])
def calculate_route():
    start_time = time.time()
    try:
        data = request.json
        city_key = data.get("city", "Mangaluru")
        start_pt = data.get("start")
        end_pt = data.get("end")
        custom_block = data.get("custom_block", "")

        router_engine.load_network_if_new(city_key)
        score, tier, submerged, warnings, green_nodes, fallback_nodes = router_engine.adapt_network_weights(
            start_pt[0], start_pt[1], custom_block
        )
        route_coords, pass_used, avoided_submerged, avoided_warn = router_engine.generate_safe_detailed_route(start_pt, end_pt, green_nodes, fallback_nodes)
        latency = (time.time() - start_time) * 1000

        if route_coords is None:
            return jsonify({
                "status": "failed",
                "message": "Evacuation path blocked. Route options completely submerged."
            }), 400

        reasoning = router_engine.generate_reasoning(tier, pass_used, avoided_submerged, avoided_warn)

        return jsonify({
            "status": "success",
            "risk_score": round(score, 2),
            "risk_tier": tier,
            "latency_ms": round(latency, 2),
            "route": route_coords,
            "submerged_layers": submerged,
            "warning_layers": warnings,
            "reasoning": reasoning
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)