import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import sys
import math
import logging
import json
import urllib.request
from typing import Dict, List, Tuple
from flask import Flask, request, jsonify
import networkx as nx
import numpy as np
from scipy.spatial import KDTree, ConvexHull
import osmnx as ox
from gis_engine.satellite.sentinel_loader import SentinelFloodLoader
from gis_engine.osm.osm_loader import OSMLoader
from gis_engine.osm.road_extractor import RoadExtractor
from gis_engine.graph.graph_builder import GraphBuilder
from gis_engine.graph.node_mapper import NodeMapper
from gis_engine.osm.hospital_extractor import HospitalExtractor
from gis_engine.shelters.shelter_mapper import ShelterMapper


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configure OSMnx to be quiet
ox.settings.log_console = False
ox.settings.use_cache = True

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ============================================================================
# GEOMETRY & SPATIAL HELPERS
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in meters"""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm to determine if a point (lat, lon) is inside a polygon"""
    num_vertices = len(polygon)
    inside = False
    p1lat, p1lon = polygon[0]
    for i in range(1, num_vertices + 1):
        p2lat, p2lon = polygon[i % num_vertices]
        if lon > min(p1lon, p2lon):
            if lon <= max(p1lon, p2lon):
                if lat <= max(p1lat, p2lat):
                    if p1lon != p2lon:
                        xinters = (lon - p1lon) * (p2lat - p1lat) / (p2lon - p1lon) + p1lat
                    if p1lat == p2lat or lat <= xinters:
                        inside = not inside
        p1lat, p1lon = p2lat, p2lon
    return inside

def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    return (C[0] - A[0]) * (B[1] - A[1]) > (B[0] - A[0]) * (C[1] - A[1])

def line_intersection(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

def segment_intersects_polygon(p1: Tuple[float, float], p2: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    if not polygon:
        return False
    if point_in_polygon(p1[0], p1[1], polygon) or point_in_polygon(p2[0], p2[1], polygon):
        return True
    num_vertices = len(polygon)
    for i in range(num_vertices):
        q1 = polygon[i]
        q2 = polygon[(i + 1) % num_vertices]
        if line_intersection(p1, p2, q1, q2):
            return True
    return False


def clean_name(val, default: str) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    return str(val)

def clean_int(val, default: int) -> int:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default

def extract_waterway_coordinates(osm_data: dict) -> List[Tuple[float, float]]:
    """Extract coordinates of all waterway/water nodes from downloaded OSM data"""
    water_coords = []
    
    # 1. Scan nodes directly tagged as water
    for node_id, node in osm_data.get("nodes", {}).items():
        tags = node.get("tags", {})
        if "waterway" in tags or tags.get("natural") == "water":
            water_coords.append((node["lat"], node["lon"]))
            
    # 2. Scan ways
    nodes_dict = osm_data.get("nodes", {})
    for way_id, way in osm_data.get("ways", {}).items():
        tags = way.get("tags", {})
        if "waterway" in tags or tags.get("natural") == "water":
            for nid in way.get("nodes", []):
                if nid in nodes_dict:
                    n = nodes_dict[nid]
                    water_coords.append((n["lat"], n["lon"]))
                    
    return list(set(water_coords))

def extract_waterway_geojson_features(osm_data: dict) -> List[dict]:
    """Extract waterways from OSM data as LineString GeoJSON features"""
    features = []
    nodes_dict = osm_data.get("nodes", {})
    
    for way_id, way in osm_data.get("ways", {}).items():
        tags = way.get("tags", {})
        if "waterway" in tags or tags.get("natural") == "water":
            coords = []
            for nid in way.get("nodes", []):
                if nid in nodes_dict:
                    n = nodes_dict[nid]
                    coords.append([n["lon"], n["lat"]])
            
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    },
                    "properties": {
                        "name": tags.get("name") or "Waterway",
                        "type": "waterway",
                        "waterway_type": tags.get("waterway") or tags.get("natural")
                    }
                })
    return features


# ============================================================================
# API ELEVATION FETCHING
# ============================================================================

def fetch_elevations(coords: List[Tuple[float, float]]) -> List[float]:
    """Query elevations for a list of (lat, lon) coordinates from Open-Meteo Elevation API"""
    if not coords:
        return []
    
    elevations = []
    batch_size = 100
    for i in range(0, len(coords), batch_size):
        batch = coords[i:i+batch_size]
        lats_str = ",".join(str(c[0]) for c in batch)
        lons_str = ",".join(str(c[1]) for c in batch)
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lats_str}&longitude={lons_str}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                res = json.loads(response.read().decode())
                elevations.extend(res.get("elevation", [10.0] * len(batch)))
        except Exception as e:
            logger.warning(f"Elevation API query failed: {e}. Defaulting to simulated profiles.")
            elevations.extend([10.0] * len(batch))
    return elevations

def find_safest_route(G: nx.DiGraph, start, goal, risk_penalty: float = 5.0) -> Tuple[List[int], float]:
    def cost_func(u, v, d):
        edge_data = G.get_edge_data(u, v)
        if edge_data is None:
            return float('inf')
        if edge_data.get("blocked", False):
            return float('inf')
        travel_time = edge_data.get("travel_time_s", 60.0)
        risk = edge_data.get("risk", 0.0)
        return travel_time + (risk_penalty * risk)
    
    try:
        path = nx.astar_path(G, start, goal, weight=cost_func)
        total_cost = sum(cost_func(path[i], path[i+1], G.get_edge_data(path[i], path[i+1])) for i in range(len(path) - 1))
        return path, total_cost
    except Exception:
        return [], float('inf')

# ============================================================================
# FLASK DYNAMIC SIMULATOR ROUTE
# ============================================================================

@app.route('/api/simulate', methods=['GET'])
def simulate():
    location = request.args.get('location', 'Mangaluru, Karnataka, India')
    method = request.args.get('method', 'method1')
    current_level = float(request.args.get('current_level', '8.2'))
    normal_level = float(request.args.get('normal_level', '5.0'))
    
    logger.info(f"Received simulation request for: {location} [Method: {method}]")
    
    try:
        # 1. Geocode input location
        logger.info(f"Geocoding location: {location}...")
        try:
            center_lat, center_lon = ox.geocode(location)
            logger.info(f"Geocoded successfully: ({center_lat}, {center_lon})")
        except Exception as ge:
            logger.warning(f"OSMnx geocoding failed: {ge}. Using fallback center.")
            center_lat, center_lon = 12.8717, 74.8463
            
        # Calculate bounding box (roughly 2500m radius around center)
        lat_offset = 2500.0 / 111000.0
        lon_offset = 2500.0 / (111000.0 * math.cos(math.radians(center_lat)))
        min_lat = center_lat - lat_offset
        max_lat = center_lat + lat_offset
        min_lon = center_lon - lon_offset
        max_lon = center_lon + lon_offset
        
        logger.info(f"Loading OSM data via OSMLoader for BBOX: {min_lat}, {min_lon}, {max_lat}, {max_lon}...")
        loader = OSMLoader()
        osm_data = loader.load_from_bbox(min_lat, min_lon, max_lat, max_lon)
        
        # 2. Extract road network & build DiGraph
        logger.info("Extracting road edges using custom RoadExtractor...")
        extractor = RoadExtractor(include_pedestrian=False, include_service_roads=True)
        edges = extractor.extract(osm_data)
        
        logger.info("Building custom graph using GraphBuilder...")
        builder = GraphBuilder()
        G_di = builder.build(edges, osm_data["nodes"])
        
        # Ensure backwards compatibility for node keys 'y' (latitude) and 'x' (longitude)
        for node_id in G_di.nodes():
            node_data = G_di.nodes[node_id]
            node_data["y"] = node_data.get("lat", 0.0)
            node_data["x"] = node_data.get("lon", 0.0)
            
        lats = [G_di.nodes[n]["y"] for n in G_di.nodes]
        lons = [G_di.nodes[n]["x"] for n in G_di.nodes]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # 3. Extract Waterways
        logger.info("Extracting waterways using custom helper...")
        water_coords = extract_waterway_coordinates(osm_data)
        waterway_features = extract_waterway_geojson_features(osm_data)
            
        # 4. Snap Facilities
        logger.info("Extracting and snapping facilities...")
        mapper = NodeMapper(G_di)
        facilities = {"hospitals": [], "shelters": [], "rescue_stations": []}
        
        # Hospitals snap
        hosp_extractor = HospitalExtractor(include_clinics=True)
        osm_hospitals = hosp_extractor.extract(osm_data)
        for hosp in osm_hospitals:
            if hosp.get("lat") and hosp.get("lon"):
                node = mapper.nearest_node(hosp["lat"], hosp["lon"])
                if node:
                    facilities["hospitals"].append({
                        "id": str(hosp["osm_id"]),
                        "name": clean_name(hosp.get("name"), f"Hospital ({hosp['osm_id']})"),
                        "node": node,
                        "lat": hosp["lat"],
                        "lon": hosp["lon"],
                        "capacity": clean_int(hosp.get("beds"), 100)
                    })
            
        # Shelters snap
        shelter_mapper = ShelterMapper(mapper, include_schools_as_shelters=True)
        osm_shelters = shelter_mapper.extract_from_osm(osm_data)
        for s in osm_shelters:
            facilities["shelters"].append({
                "id": str(s["osm_id"]),
                "name": clean_name(s.get("name"), f"Shelter ({s['osm_id']})"),
                "node": s["nearest_node"],
                "lat": s["lat"],
                "lon": s["lon"],
                "capacity": clean_int(s.get("capacity"), 300)
            })
            
        # Rescue Stations snap
        # Find fire stations / ambulance stations in osm_data
        for node_id, node in osm_data.get("nodes", {}).items():
            tags = node.get("tags", {})
            if tags.get("amenity") == "fire_station" or tags.get("emergency") == "ambulance_station":
                node_idx = mapper.nearest_node(node["lat"], node["lon"])
                if node_idx:
                    facilities["rescue_stations"].append({
                        "id": str(node_id),
                        "name": clean_name(tags.get("name"), f"Rescue Station ({node_id})"),
                        "node": node_idx,
                        "lat": node["lat"],
                        "lon": node["lon"]
                    })
                    
        for way_id, way in osm_data.get("ways", {}).items():
            tags = way.get("tags", {})
            if tags.get("amenity") == "fire_station" or tags.get("emergency") == "ambulance_station":
                nodes_dict = osm_data.get("nodes", {})
                way_nodes = way.get("nodes", [])
                valid_nodes = [nodes_dict[nid] for nid in way_nodes if nid in nodes_dict]
                if valid_nodes:
                    lat = sum(n["lat"] for n in valid_nodes) / len(valid_nodes)
                    lon = sum(n["lon"] for n in valid_nodes) / len(valid_nodes)
                    node_idx = mapper.nearest_node(lat, lon)
                    if node_idx:
                        facilities["rescue_stations"].append({
                            "id": str(way_id),
                            "name": clean_name(tags.get("name"), f"Rescue Station ({way_id})"),
                            "node": node_idx,
                            "lat": lat,
                            "lon": lon
                        })
                        
        # Add fallbacks if empty
        if not facilities["hospitals"]:
            h_coords = (center_lat + 0.005, center_lon + 0.005)
            node = mapper.nearest_node(*h_coords)
            facilities["hospitals"].append({
                "id": "H1-fallback", "name": "Central Hospital",
                "node": node,
                "lat": h_coords[0], "lon": h_coords[1], "capacity": 200
            })
        if not facilities["shelters"]:
            s_coords = (center_lat - 0.005, center_lon - 0.005)
            node = mapper.nearest_node(*s_coords)
            facilities["shelters"].append({
                "id": "S1-fallback", "name": "Community Shelter",
                "node": node,
                "lat": s_coords[0], "lon": s_coords[1], "capacity": 500
            })
        if not facilities["rescue_stations"]:
            station_coords = (center_lat - 0.002, center_lon + 0.002)
            node = mapper.nearest_node(*station_coords)
            facilities["rescue_stations"].append({
                "id": "RS1-fallback", "name": "Rescue Station A",
                "node": node,
                "lat": station_coords[0], "lon": station_coords[1]
            })

        
        # 4. Fetch Elevations
        logger.info("Fetching elevations from API...")
        unique_nodes = list(G_di.nodes())
        coords_list = [(G_di.nodes[n]["y"], G_di.nodes[n]["x"]) for n in unique_nodes]
        elevations = fetch_elevations(coords_list)
        
        node_elevations = {unique_nodes[i]: elevations[i] for i in range(len(unique_nodes))}
        for n, elev in node_elevations.items():
            G_di.nodes[n]["elevation"] = elev

        # 5. Fetch Weather
        logger.info("Fetching live weather from Open-Meteo...")
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={center_lat}&longitude={center_lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
        try:
            with urllib.request.urlopen(weather_url, timeout=5) as response:
                w_data = json.loads(response.read().decode())
                current = w_data.get("current", {})
                temp = current.get("temperature_2m", 27.5)
                humidity = current.get("relative_humidity_2m", 85)
                wind_speed = current.get("wind_speed_10m", 6.0)
                rain_1h = current.get("precipitation", 0.0)
                weather_desc = "Rainy conditions" if rain_1h > 0 else "Fair weather"
        except Exception:
            temp, humidity, wind_speed, rain_1h, weather_desc = 27.5, 92, 8.5, 12.5, "heavy rain (fallback)"

        # Override rainfall rate if specified in the API request params
        rain_override = request.args.get("rain_1h")
        if rain_override is not None:
            try:
                rain_1h = float(rain_override)
                weather_desc = f"Simulated rain ({rain_1h} mm/h)"
            except ValueError:
                pass

        # 6. Apply Inundation Model & Calculate Risk
        blocked_edges = []
        slowed_edges = []
        flooded_points = []
        
        # Water KDTree for river proximity checks
        water_tree = None
        if water_coords:
            water_tree = KDTree(np.array(water_coords))
            
        extra_water = current_level - normal_level
        flood_threshold_elev = normal_level + extra_water
        spread_radius_m = max(100.0, extra_water * 150.0) if method == 'method2' else min(500.0, 200.0 + (rain_1h * 15.0))
        
        flood_polygon = []
        if method == 'method1':
            logger.info("Initializing Sentinel-1 SAR flood loader...")
            sentinel_loader = SentinelFloodLoader()
            # Generate the flood polygon from Sentinel-1 SAR imagery simulation
            flood_polygon = sentinel_loader.get_latest_flood_polygon(
                center_lat, center_lon, water_coords=water_coords, rain_1h=rain_1h
            )
            
            # Predict & scale waterlogging buffer distance based on rainfall
            buffer_distance_m = 200.0
            if rain_1h > 0:
                buffer_distance_m = min(500.0, 200.0 + (rain_1h * 15.0))
        
        for u, v, d in G_di.edges(data=True):
            u_data = G_di.nodes[u]
            v_data = G_di.nodes[v]
            p1 = (u_data["y"], u_data["x"])
            p2 = (v_data["y"], v_data["x"])
            
            length_m = d.get("length") or haversine_distance(p1[0], p1[1], p2[0], p2[1])
            d["length_m"] = length_m
            # Calculate speed based on standard 40km/h fallback if not specified
            speed_kph = 40.0
            if "maxspeed" in d:
                try:
                    if isinstance(d["maxspeed"], list):
                        speed_kph = float(d["maxspeed"][0])
                    else:
                        speed_kph = float(d["maxspeed"])
                except Exception:
                    pass
            d["travel_time_s"] = length_m / (speed_kph / 3.6)
            
            mid_lat = (p1[0] + p2[0]) / 2.0
            mid_lon = (p1[1] + p2[1]) / 2.0
            
            # Distance to water
            if water_tree:
                dist_deg, _ = water_tree.query([mid_lat, mid_lon])
                river_distance = dist_deg * 111_000.0
            else:
                river_distance = haversine_distance(mid_lat, mid_lon, center_lat, center_lon)
            d["river_distance"] = river_distance
            
            elevation = (u_data.get("elevation", 10.0) + v_data.get("elevation", 10.0)) / 2.0
            
            # Flooded checks
            is_flooded = False
            is_slowed = False
            
            if method == 'method1':
                # Check segment intersection with flood polygon
                intersects_flood = segment_intersects_polygon(p1, p2, flood_polygon)
                
                # Check distance to flood polygon to evaluate buffer zone
                dist_to_poly = float('inf')
                for vertex in flood_polygon:
                    dist_u = haversine_distance(p1[0], p1[1], vertex[0], vertex[1])
                    dist_v = haversine_distance(p2[0], p2[1], vertex[0], vertex[1])
                    dist_to_poly = min(dist_to_poly, dist_u, dist_v)
                
                if intersects_flood:
                    flood_probability = 1.0
                elif dist_to_poly <= buffer_distance_m:
                    base_prob = 0.5 * (1.0 - (dist_to_poly / buffer_distance_m))
                    flood_probability = base_prob + (0.5 * (1.0 - math.exp(-0.2 * rain_1h)))
                    flood_probability = min(0.99, flood_probability)
                else:
                    susceptibility = 1.0 / (1.0 + math.exp(0.3 * elevation + 0.005 * river_distance - 4.0))
                    flood_probability = susceptibility * (1.0 - math.exp(-0.1 * rain_1h))
                
                is_flooded = (flood_probability >= 0.85)
                is_slowed = (flood_probability > 0.3) and not is_flooded
            else:
                is_flooded = (river_distance <= spread_radius_m) and (elevation <= flood_threshold_elev)
                is_slowed = (river_distance <= spread_radius_m + 200.0) and (elevation <= flood_threshold_elev + 1.5)
                
            if is_flooded:
                d["blocked"] = True
                d["risk"] = 1.0
                blocked_edges.append((u, v))
                flooded_points.append(p1)
                flooded_points.append(p2)
            else:
                d["blocked"] = False
                d["risk"] = 0.5 if is_slowed else 0.0
                if is_slowed:
                    slowed_edges.append((u, v))
                    
        # 7. Create Flood Polygon using Convex Hull
        if not flood_polygon or method != 'method1':
            flood_polygon = []
            if len(flooded_points) >= 3:
                try:
                    points_arr = np.array(list(set(flooded_points)))
                    if len(points_arr) >= 3:
                        hull = ConvexHull(points_arr)
                        flood_polygon = [tuple(points_arr[idx]) for idx in hull.vertices]
                        flood_polygon.append(flood_polygon[0])
                except Exception:
                    pass
            
            if not flood_polygon and flooded_points:
                lats_fl = [p[0] for p in flooded_points]
                lons_fl = [p[1] for p in flooded_points]
                flood_polygon = [
                    (min(lats_fl), min(lons_fl)),
                    (max(lats_fl), min(lons_fl)),
                    (max(lats_fl), max(lons_fl)),
                    (min(lats_fl), max(lons_fl)),
                    (min(lats_fl), min(lons_fl))
                ]

        # 8. Calculate Routes (Normal, Detour, Shelter)
        start_node = facilities["rescue_stations"][0]["node"]
        
        # Snag coordinate-snapped incident
        incident_lat = center_lat + 0.003
        incident_lon = center_lon + 0.003
        incident_node = mapper.nearest_node(incident_lat, incident_lon)
        
        # Normal Route (before flood)
        G_normal = G_di.copy()
        for u, v, d in G_normal.edges(data=True):
            d["blocked"] = False
            d["risk"] = 0.0
        route_before, cost_before = find_safest_route(G_normal, start_node, incident_node)
        
        # Detour Route (after flood)
        route_after, cost_after = find_safest_route(G_di, start_node, incident_node)
        
        # Shelter Route
        route_shelter = []
        if facilities["shelters"]:
            target_shelter = facilities["shelters"][0]
            route_shelter, _ = find_safest_route(G_di, start_node, target_shelter["node"])
            
        # 9. Format features into Leaflet GeoJSON
        logger.info("Assembling GeoJSON layers...")
        features = []
        
        # Helper to convert path to GeoJSON points
        def route_to_coords(route: List[int]):
            return [[G_di.nodes[n]["x"], G_di.nodes[n]["y"]] for n in route if n in G_di]
            
        # Flood Polygon
        if flood_polygon:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[ [pt[1], pt[0]] for pt in flood_polygon ]]
                },
                "properties": {
                    "name": "Active Flood Zone",
                    "type": "flood_zone"
                }
            })
            
        # Waterways
        if waterway_features:
            features.extend(waterway_features)
            
        # Normal Route
        if route_before:
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": route_to_coords(route_before)},
                "properties": {"name": "Safe Conditions Route", "type": "route_before"}
            })
            
        # Detour Route
        if route_after:
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": route_to_coords(route_after)},
                "properties": {"name": "Alternative Route (Detour)", "type": "route_after"}
            })
            
        # Shelter Route
        if route_shelter:
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": route_to_coords(route_shelter)},
                "properties": {"name": "Shelter Transport Route", "type": "route_shelter"}
            })
            
        # Incident Marker
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [incident_lon, incident_lat]},
            "properties": {"name": "Active Incident", "type": "incident", "severity": "Critical"}
        })
        
        # Facilities
        for station in facilities["rescue_stations"]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [station["lon"], station["lat"]]},
                "properties": {"name": station["name"], "type": "rescue_station"}
            })
        for hosp in facilities["hospitals"]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [hosp["lon"], hosp["lat"]]},
                "properties": {"name": hosp["name"], "type": "hospital", "capacity": hosp["capacity"]}
            })
        for shelter in facilities["shelters"]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [shelter["lon"], shelter["lat"]]},
                "properties": {"name": shelter["name"], "type": "shelter", "capacity": shelter["capacity"]}
            })
            
        # Assembly payload
        weather_meta = {
            "temp": temp,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "rain_1h": rain_1h,
            "description": weather_desc
        }
        route_analysis = {
            "cost_before": cost_before,
            "cost_after": cost_after if route_after else cost_before,
            "time_increase_pct": ((cost_after - cost_before) / cost_before) * 100 if route_after and cost_before > 0 else 0.0
        }
        
        response_payload = {
            "type": "FeatureCollection",
            "features": features,
            "weather_metadata": weather_meta,
            "route_analysis": route_analysis
        }
        
        logger.info("Simulation successfully completed!")
        return jsonify(response_payload)
        
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Sahyadri Disaster Routing Simulator Backend Server...")
    app.run(host='0.0.0.0', port=8000, debug=False)
