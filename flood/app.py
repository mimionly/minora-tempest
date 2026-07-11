import os
import time
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
    "Mangaluru": {"lat": 12.8701, "lon": 74.8800, "radius": 4000}, # Optimized radius for tight density visual
    "Patna": {"lat": 25.5941, "lon": 85.1376, "radius": 4000}
}

class CoastalFloodRouter:
    def __init__(self):
        try:
            self.clf = joblib.load("flood_risk_classifier.joblib")
            self.reg = joblib.load("flood_risk_regressor.joblib")
            print("Successfully loaded district flood risk ML models.")
        except FileNotFoundError:
            print("ML model binaries not found. Defaulting to mathematical algorithm fallbacks.")
            self.clf, self.reg = None, None
            
        self.graph = None
        self.current_location = ""
        self.baseline_features = {
            "Parmanent_Water": 2.5,
            "fatality_rate": 1.5,
            "injury_rate": 0.3,
            "Population": 650000
        }

    def load_network_if_new(self, key_name):
        if self.current_location == key_name and self.graph is not None:
            return
            
        print(f"Loading new regional topology for: {key_name}...")
        config = CITY_COORDINATES[key_name]
        
        self.graph = ox.graph_from_point(
            (config["lat"], config["lon"]), 
            dist=config["radius"], 
            network_type="drive"
        )
        self.current_location = key_name
        
        for u, v, k, data in self.graph.edges(data=True, keys=True):
            data['base_length'] = data.get('length', 1.0)
            data['current_weight'] = data['base_length']
            data['is_blocked'] = False

    def get_all_nodes(self):
        """Extracts all intersections/nodes from the active graph layer"""
        if self.graph is None:
            return []
        return [[self.graph.nodes[n]['y'], self.graph.nodes[n]['x']] for n in self.graph.nodes]

    def fetch_keyless_weather(self, lat, lon):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(url, timeout=5).json()
            current = response.get("current_weather", {})
            rain_val = current.get("windspeed", 8.0) 
            simulated_flooded = min(max(rain_val * 1.5, 4.0), 45.0)
            return {
                "Percent_Flooded_Area": simulated_flooded,
                "Mean_Flood_Duration": min(simulated_flooded * 0.8, 25.0)
            }
        except Exception:
            return {"Percent_Flooded_Area": 28.0, "Mean_Flood_Duration": 12.0}

    def adapt_network_weights(self, center_lat, center_lon):
        weather = self.fetch_keyless_weather(center_lat, center_lon)
        payload = pd.DataFrame([{
            "Percent_Flooded_Area": weather["Percent_Flooded_Area"],
            "Parmanent_Water": self.baseline_features["Parmanent_Water"],
            "Corrected_Percent_Flooded_Area": weather["Percent_Flooded_Area"] - self.baseline_features["Parmanent_Water"],
            "fatality_rate": self.baseline_features["fatality_rate"],
            "injury_rate": self.baseline_features["injury_rate"],
            "Mean_Flood_Duration": weather["Mean_Flood_Duration"],
            "Population": self.baseline_features["Population"]
        }])

        if self.clf and self.reg:
            risk_score = self.reg.predict(payload)[0]
            risk_tier = self.clf.predict(payload)[0]
        else:
            risk_score = 72.4
            risk_tier = "Very High"

        for u, v, k, data in self.graph.edges(data=True, keys=True):
            node_data = self.graph.nodes[u]
            edge_lat = node_data.get('y', center_lat)
            spatial_risk = risk_score * (1.0 + (np.sin(edge_lat * 2000) * 0.2))
            
            if spatial_risk > 82.0:
                data['is_blocked'] = True
                data['current_weight'] = float('inf')
            elif spatial_risk > 50.0:
                data['is_blocked'] = False
                data['current_weight'] = data['base_length'] * (1.0 + (spatial_risk / 10.0))
            else:
                data['is_blocked'] = False
                data['current_weight'] = data['base_length']
                
        return risk_score, risk_tier

    def generate_safe_route(self, start_coords, end_coords):
        orig_node = ox.nearest_nodes(self.graph, X=start_coords[1], Y=start_coords[0])
        dest_node = ox.nearest_nodes(self.graph, X=end_coords[1], Y=end_coords[0])
        try:
            path = nx.shortest_path(self.graph, source=orig_node, target=dest_node, weight='current_weight')
            return [[self.graph.nodes[n]['y'], self.graph.nodes[n]['x']] for n in path]
        except nx.NetworkXNoPath:
            return None

router_engine = CoastalFloodRouter()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/route", methods=["POST"])
def calculate_route():
    start_time = time.time()
    data = request.json
    
    city_key = data.get("city", "Mangaluru")
    start_pt = data.get("start")
    end_pt = data.get("end")
    
    router_engine.load_network_if_new(city_key)
    score, tier = router_engine.adapt_network_weights(start_pt[0], start_pt[1])
    route_coords = router_engine.generate_safe_route(start_pt, end_pt)
    
    # Get all active nodes in the map segment
    network_nodes = router_engine.get_all_nodes()
    
    latency = (time.time() - start_time) * 1000
    
    if route_coords is None:
        return jsonify({"status": "failed", "message": "All escape routes submerged."}), 400
        
    return jsonify({
        "status": "success",
        "risk_score": round(score, 2),
        "risk_tier": tier,
        "latency_ms": round(latency, 2),
        "route": route_coords,
        "nodes": network_nodes
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)