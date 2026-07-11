import os
import time
import requests
import joblib
import networkx as nx
import osmnx as ox
import pandas as pd
import numpy as np
import heapq
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Enforce strict global in-memory caching layers
ox.settings.use_cache = True
ox.settings.log_console = False

CITY_COORDINATES = {
    "Mangaluru": {"lat": 12.8701, "lon": 74.8800, "radius": 10000},
    "Udupi": {"lat": 13.3409, "lon": 74.7426, "radius": 10000}
}

COASTAL_HAZARD_RIVERS = np.array([
    [12.8480, 74.8450],  # Netravati Basin
    [12.8920, 74.8280],  # Gurupura Basin
    [13.3164, 74.7290],  # Udyavara River Outlet
    [13.3712, 74.7485]   # Swarna River Channel
])

SPEED_PROFILES = {"walking": 4.5, "bike": 18.0, "car": 35.0, "bus": 22.0}

class UltraLowLatencyRouter:
    def __init__(self):
        try:
            self.reg = joblib.load("flood_risk_regressor.joblib")
            print("Successfully loaded calibrated flood risk ML Regressor.")
        except FileNotFoundError:
            self.reg = None
            
        self.graphs = {}
        self.baseline_features = {
            "Parmanent_Water": 2.8,
            "fatality_rate": 6.77,
            "injury_rate": 1.93,
            "Population": 620000
        }
        # Warm up maps instantly into memory during initialization to eliminate request lag
        for city in CITY_COORDINATES:
            self._preload_map(city)

    def _preload_map(self, key_name):
        config = CITY_COORDINATES[key_name]
        print(f"Pre-loading and warming up {key_name} topology cache...")
        G = ox.graph_from_point((config["lat"], config["lon"]), dist=config["radius"], network_type="drive")
        
        # Optimize edge tracking arrays inside RAM
        for u, v, k, data in G.edges(data=True, keys=True):
            data['base_length'] = data.get('length', 1.0)
            data['current_weight'] = data['base_length']
            data['is_blocked'] = False
            data['risk_score'] = 0.0
        self.graphs[key_name] = G

    def fetch_live_weather(self, lat, lon):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(url, timeout=3).json()
            current = response.get("current_weather", {})
            temp = current.get("temperature", 27.0)
            wind = current.get("windspeed", 14.0)
            wcode = current.get("weathercode", 0)
            
            w_desc = "Clear/Baseline Weather"
            if wcode in [1, 2, 3]: w_desc = "Partly Cloudy"
            elif wcode in [51, 53, 55, 61, 63, 65]: w_desc = "Active Monsoon Rain"
            elif wcode in [80, 81, 82]: w_desc = "Torrential Storm Conditions"
            
            return {"Percent_Flooded_Area": min(max(14.0 + (wind % 7), 10.0), 28.0), "Mean_Flood_Duration": 9.5, "temperature": temp, "windspeed": wind, "description": w_desc}
        except Exception:
            return {"Percent_Flooded_Area": 18.0, "Mean_Flood_Duration": 10.5, "temperature": 26.5, "windspeed": 12.0, "description": "Coastal Overcast"}

    def adapt_network_weights_vectorized(self, city_key, center_lat, center_lon, custom_block_text=""):
        weather = self.fetch_live_weather(center_lat, center_lon)
        G = self.graphs[city_key]

        payload = pd.DataFrame([{
            "Percent_Flooded_Area": weather["Percent_Flooded_Area"],
            "Parmanent_Water": self.baseline_features["Parmanent_Water"],
            "Corrected_Percent_Flooded_Area": weather["Percent_Flooded_Area"] - self.baseline_features["Parmanent_Water"],
            "fatality_rate": self.baseline_features["fatality_rate"],
            "injury_rate": self.baseline_features["injury_rate"],
            "Mean_Flood_Duration": weather["Mean_Flood_Duration"],
            "Population": self.baseline_features["Population"]
        }])

        district_base_score = float(self.reg.predict(payload)[0]) if self.reg else 50.5
        block_keyword = custom_block_text.strip().lower()
        
        submerged_edges, warn_edges = [], []
        total_risk = 0.0
        
        # HIGH SPEED CACHE PROCESSING: Pull node position arrays instantly via NumPy matrix broadcasting
        node_ids = list(G.nodes)
        node_coords = np.array([[G.nodes[n]['y'], G.nodes[n]['x']] for n in node_ids])
        
        # Compute distances across all nodes to closest river targets in one vector calculation
        dists = np.min(np.sqrt(np.sum((node_coords[:, np.newaxis, :] - COASTAL_HAZARD_RIVERS[np.newaxis, :, :]) ** 2, axis=2)), axis=1)
        node_risk_map = dict(zip(node_ids, dists))

        for u, v, k, data in G.edges(data=True, keys=True):
            min_dist = node_risk_map[u]
            proximity_factor = 1.45 * (1.0 - (min_dist / 0.016)) if min_dist < 0.016 else 0.38
            
            local_road_risk = district_base_score * proximity_factor
            total_risk += local_road_risk
            
            data['is_blocked'] = False
            data['risk_score'] = local_road_risk
            
            # Map structural geometry arrays
            geom = [[y, x] for x, y in zip(data['geometry'].xy[0], data['geometry'].xy[1])] if 'geometry' in data else [[G.nodes[u]['y'], G.nodes[u]['x']], [G.nodes[v]['y'], G.nodes[v]['x']]]

            edge_name = str(data.get('name', '')).lower()
            if block_keyword and (block_keyword in edge_name):
                data['is_blocked'] = True; data['current_weight'] = float('inf')
                submerged_edges.append(geom)
                continue

            if local_road_risk >= 56.0:
                data['is_blocked'] = True; data['current_weight'] = float('inf')
                submerged_edges.append(geom)
            elif local_road_risk >= 34.0:
                data['current_weight'] = data['base_length'] * (1.0 + (local_road_risk / 2.8))
                warn_edges.append(geom)
            else:
                data['current_weight'] = data['base_length']
        
        avg_risk = total_risk / max(len(G.edges), 1)
        tier = "Very High" if avg_risk >= 60.0 else "High" if avg_risk >= 45.0 else "Medium" if avg_risk >= 25.0 else "Low"
        return avg_risk, tier, submerged_edges, warn_edges, weather

    def _haversine_heuristic(self, G, node_u, node_v):
        lat1, lon1 = G.nodes[node_u]['y'], G.nodes[node_u]['x']
        lat2, lon2 = G.nodes[node_v]['y'], G.nodes[node_v]['x']
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        a = np.sin(np.radians(lat2 - lat1)/2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(np.radians(lon2 - lon1)/2.0)**2
        return 6371000.0 * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

    def a_star_search(self, city_key, start_node, target_node):
        G = self.graphs[city_key]
        open_set = []
        heapq.heappush(open_set, (0.0, 0.0, start_node))
        came_from = {}
        g_score = {node: float('inf') for node in G.nodes}
        g_score[start_node] = 0.0
        
        while open_set:
            _, current_g, current = heapq.heappop(open_set)
            if current == target_node:
                path = []
                while current in came_from:
                    path.append(current); current = came_from[current]
                path.append(start_node)
                return path[::-1]
                
            if current_g > g_score[current]: continue
                
            for neighbor in G.neighbors(current):
                edge_data = G.get_edge_data(current, neighbor)
                data = edge_data[0] if 0 in edge_data else list(edge_data.values())[0]
                weight = data.get('current_weight', float('inf'))
                if weight == float('inf'): continue
                    
                tentative_g = current_g + weight
                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current; g_score[neighbor] = tentative_g
                    f = tentative_g + self._haversine_heuristic(G, neighbor, target_node)
                    heapq.heappush(open_set, (f, tentative_g, neighbor))
        return None

    def generate_safe_detailed_route(self, city_key, start_coords, end_coords):
        G = self.graphs[city_key]
        orig_node = ox.nearest_nodes(G, X=start_coords[1], Y=start_coords[0])
        dest_node = ox.nearest_nodes(G, X=end_coords[1], Y=end_coords[0])
        path = self.a_star_search(city_key, orig_node, dest_node)
        
        if not path: return None, 0, {}
            
        detailed_coords = []
        total_dist = 0.0
        times = {mode: 0.0 for mode in SPEED_PROFILES}

        for u, v in zip(path[:-1], path[1:]):
            edge_data = G.get_edge_data(u, v)
            data = edge_data[0] if 0 in edge_data else list(edge_data.values())[0]
            length = data.get('base_length', 1.0)
            total_dist += length
            road_risk = data.get('risk_score', 0.0)
            
            p_mult = 1.0 + (road_risk / 15.0) if road_risk >= 34.0 else 1.0
            for mode, speed in SPEED_PROFILES.items():
                times[mode] += (length / ((speed * 1000) / 60.0)) * (p_mult if mode != "walking" else (1.0 + (road_risk / 25.0)))

            if 'geometry' in data:
                detailed_coords.extend([[y, x] for x, y in zip(data['geometry'].xy[0], data['geometry'].xy[1])])
            else:
                detailed_coords.append([G.nodes[u]['y'], G.nodes[u]['x']])
                
        detailed_coords.append([G.nodes[path[-1]]['y'], G.nodes[path[-1]]['x']])
        return detailed_coords, round(total_dist / 1000.0, 2), {m: round(t) for m, t in times.items()}

router_engine = UltraLowLatencyRouter()

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/api/route', methods=['POST'])
def calculate_route():
    start_time = time.time()
    data = request.json
    city_key = data.get("city", "Mangaluru")
    
    # Accelerated processing using pre-warmed cache arrays
    score, tier, submerged, warnings, weather = router_engine.adapt_network_weights_vectorized(city_key, data['start'][0], data['start'][1], data.get("custom_block", ""))
    route_coords, dist_km, times = router_engine.generate_safe_detailed_route(city_key, data['start'], data['end'])
    
    if route_coords is None:
        return jsonify({"status": "failed", "message": "All paths submerged."}), 400
        
    return jsonify({
        "status": "success", "risk_score": round(score, 2), "risk_tier": tier, 
        "latency_ms": round((time.time() - start_time) * 1000, 2),
        "route": route_coords, "submerged_layers": submerged, "warning_layers": warnings, 
        "weather": weather, "distance_km": dist_km, "travel_times": times
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)  # Turn off reloader to protect warmed vectors from wiping