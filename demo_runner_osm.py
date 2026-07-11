#!/usr/bin/env python3
"""
Sahyadri Disaster Routing System — Real OpenStreetMap (OSM) Demo
================================================================

This demo showcases:
1. Real road network loading for Mangaluru using the project's native OSMLoader & GraphBuilder
2. Mapping mock facility coordinate pairs to the nearest real graph nodes using NodeMapper
3. A* pathfinding on the real OSM network using computed travel-time weights
4. Simulating a localized flood event blocking roads within a geographic radius
5. Dynamic rerouting after flooding
6. Multi-vehicle rescue dispatch
7. Evacuation planning to nearby shelters
"""

import sys
import time
import logging
from typing import Dict, List, Tuple
import networkx as nx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Import the project's native GIS components
try:
    from gis_engine.osm.osm_loader import OSMLoader
    from gis_engine.osm.road_extractor import RoadExtractor
    from gis_engine.graph.graph_builder import GraphBuilder
    from gis_engine.graph.node_mapper import NodeMapper
    from gis_engine.osm.hospital_extractor import HospitalExtractor
    from gis_engine.shelters.shelter_mapper import ShelterMapper
    from gis_engine.weather.openweather_loader import get_openweather_current
    from gis_engine.satellite.sentinel_loader import SentinelFloodLoader
    from gis_engine.emergency.emergency_feed import EmergencyFeed
except ImportError as e:
    logger.error(f"Failed to import gis_engine components: {e}")
    logger.error("Make sure you are running this from the workspace root directory.")
    sys.exit(1)


# ============================================================================
# UTILITIES
# ============================================================================

def load_env(filepath: str = ".env") -> Dict[str, str]:
    """Simple parser to load key-value pairs from .env without dependencies"""
    import os
    env = {}
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in meters between two lat/lon points"""
    from math import radians, sin, cos, sqrt, asin
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlam/2)**2
    return R * 2 * asin(sqrt(a))


def route_to_gps_path(G: nx.DiGraph, route: List[int]) -> List[Tuple[float, float]]:
    """Convert a list of node IDs to a list of (latitude, longitude) coordinate tuples"""
    path = []
    for node in route:
        if node in G:
            path.append((G.nodes[node]["lat"], G.nodes[node]["lon"]))
    return path


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
    """Check if three points are listed in counter-clockwise order"""
    return (C[0] - A[0]) * (B[1] - A[1]) > (B[0] - A[0]) * (C[1] - A[1])


def line_intersection(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    """Check if line segment p1-p2 intersects line segment p3-p4"""
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def segment_intersects_polygon(p1: Tuple[float, float], p2: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Check if a line segment p1-p2 intersects or is fully inside a polygon"""
    # 1. If either endpoint is inside the polygon, it intersects
    if point_in_polygon(p1[0], p1[1], polygon) or point_in_polygon(p2[0], p2[1], polygon):
        return True
    
    # 2. Check if the segment intersects any of the boundary segments of the polygon
    num_vertices = len(polygon)
    for i in range(num_vertices):
        q1 = polygon[i]
        q2 = polygon[(i + 1) % num_vertices]
        if line_intersection(p1, p2, q1, q2):
            return True
            
    return False


# ============================================================================
# ROUTING ALGORITHMS
# ============================================================================

def find_safest_route(G: nx.DiGraph, start, goal, risk_penalty: float = 5.0) -> Tuple[List[int], float]:
    """
    Find the safest route using A* with disaster risk awareness on the real network.
    
    Cost = travel_time_s + risk_penalty * risk
    """
    def cost_func(u, v, d):
        edge_data = G.get_edge_data(u, v)
        if edge_data is None:
            return float('inf')
        if edge_data.get("blocked", False):
            return float('inf')  # Impassable
        
        travel_time = edge_data.get("travel_time_s", 60.0)
        risk = edge_data.get("risk", 0.0)
        return travel_time + (risk_penalty * risk)
    
    def h_func(u, v):
        if u not in G or goal not in G:
            return 0.0
        u_data = G.nodes[u]
        goal_data = G.nodes[goal]
        dist_m = haversine_distance(u_data["lat"], u_data["lon"], goal_data["lat"], goal_data["lon"])
        # Assume 50 kph average speed for heuristic (admissible)
        return (dist_m / 1000.0) / 50.0 * 3600.0
    
    try:
        path = nx.astar_path(G, start, goal, heuristic=h_func, weight=cost_func)
        
        # Calculate total cost
        total_cost = 0.0
        for i in range(len(path) - 1):
            edge_data = G.get_edge_data(path[i], path[i+1])
            if edge_data.get("blocked", False):
                return [], float('inf')
            total_cost += edge_data.get("travel_time_s", 60.0) + (risk_penalty * edge_data.get("risk", 0.0))
            
        return path, total_cost
    except nx.NetworkXNoPath:
        return [], float('inf')


def print_route_details(path: List[int], G: nx.DiGraph, cost: float) -> None:
    """Display detailed segment routing information"""
    if not path:
        logger.warning("❌ No route found (all paths blocked or unreachable)")
        return
    
    logger.info(f"✓ Route found ({len(path)-1} segments, cost: {cost:.1f}s / {cost/60:.1f} min)")
    
    total_dist = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge_data = G.get_edge_data(u, v)
        dist = edge_data.get("length_m", 0.0)
        travel = edge_data.get("travel_time_s", 0.0)
        blocked = "🚫 BLOCKED" if edge_data.get("blocked") else ""
        name = edge_data.get("name") or "Unnamed Road"
        total_dist += dist
        if i < 5 or i >= len(path) - 2: # Keep output brief
            logger.info(f"    Node {u} → Node {v} ({name}): {dist:.1f}m, {travel:.1f}s {blocked}")
        elif i == 5:
            logger.info("    ... [intermediate segments omitted for brevity] ...")
            
    logger.info(f"  Total distance: {total_dist:.1f}m ({total_dist/1000:.2f}km)")


# ============================================================================
# DYNAMIC PHYSICAL RISK MODEL
# ============================================================================

def apply_dynamic_risk_model(G: nx.DiGraph, flood_polygon: List[Tuple[float, float]], rain_1h: float, center_lat: float, center_lon: float, buffer_distance_m: float) -> Tuple[List, List]:
    """
    Computes physical risk attributes for every edge segment in the road network:
    - length: actual road length
    - speed: standard free-flow speed
    - rain: active hourly rainfall
    - elevation: simulated geographic elevation profile
    - slope: segment steepness
    - river_distance: distance to simulated river corridor
    - flood_probability: calculated risk of inundation
    - risk: cumulative hazard index (flood + slope landslide risk)
    - blocked: True if flood probability is high
    """
    import math
    blocked_edges = []
    slowed_edges = []
    
    # Range of coordinates for scaling mock elevation model
    lats = [G.nodes[n]["lat"] for n in G.nodes]
    lons = [G.nodes[n]["lon"] for n in G.nodes]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    lon_span = max(0.001, max_lon - min_lon)
    
    for u, v, d in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        p1 = (u_data["lat"], u_data["lon"])
        p2 = (v_data["lat"], v_data["lon"])
        
        # 1. Length
        length_m = d.get("length_m") or d.get("length") or haversine_distance(p1[0], p1[1], p2[0], p2[1])
        d["length"] = length_m
        
        # 2. Speed (mps)
        travel_time_s = d.get("travel_time_s", 60.0)
        speed_mps = length_m / max(1.0, travel_time_s)
        d["speed"] = speed_mps
        
        # 3. Rain
        d["rain"] = rain_1h
        
        # 4. Elevation (simulates coastal river valley rising up to inland hills)
        # Sea is west (min_lon), hills are east (max_lon)
        mid_lat = (p1[0] + p2[0]) / 2.0
        mid_lon = (p1[1] + p2[1]) / 2.0
        elev_u = 2.0 + 40.0 * ((p1[1] - min_lon) / lon_span)
        elev_v = 2.0 + 40.0 * ((p2[1] - min_lon) / lon_span)
        elevation = (elev_u + elev_v) / 2.0
        d["elevation"] = elevation
        
        # 5. Slope
        slope = (elev_v - elev_u) / max(1.0, length_m)
        d["slope"] = slope
        
        # 6. River Distance
        # Perpendicular distance in degrees to the river corridor line
        # Equation: lat = center_lat + (lon - center_lon) - 0.002
        d_deg = abs(mid_lat - (center_lat + (mid_lon - center_lon) - 0.002)) / math.sqrt(2.0)
        river_distance = d_deg * 111_000.0  # Convert to meters
        d["river_distance"] = river_distance
        
        # 7. Flood Probability
        # First, check if the segment intersects the Sentinel-1 flood polygon
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
            # Linear decay inside buffer
            base_prob = 0.5 * (1.0 - (dist_to_poly / buffer_distance_m))
            # Scale up with rainfall
            flood_probability = base_prob + (0.5 * (1.0 - math.exp(-0.2 * rain_1h)))
            flood_probability = min(0.99, flood_probability)
        else:
            # Outside flood and buffer, depends on low elevation and proximity to river combined with rain
            susceptibility = 1.0 / (1.0 + math.exp(0.3 * elevation + 0.005 * river_distance - 4.0))
            flood_probability = susceptibility * (1.0 - math.exp(-0.1 * rain_1h))
            
        d["flood_probability"] = flood_probability
        
        # 8. Cumulative Risk
        risk = flood_probability
        # Add risk of landslide/runoff on steep hills during heavy rain
        if rain_1h > 5.0 and abs(slope) > 0.02:
            risk += 0.25 * min(1.0, abs(slope) * 10.0)
            
        risk = min(1.0, risk)
        d["risk"] = risk
        
        # 9. Blocked state
        if flood_probability >= 0.85:
            d["blocked"] = True
            blocked_edges.append((u, v, d.get("name") or "Unnamed Road"))
        else:
            d["blocked"] = False
            if risk > 0.3:
                slowed_edges.append((u, v, d.get("name") or "Unnamed Road"))
                
    return blocked_edges, slowed_edges


# ============================================================================
# FLEET DISPATCH & EVACUATION
# ============================================================================

def dispatch_rescue_fleet(G: nx.DiGraph, facilities: Dict, rescue_requests: List[int]) -> None:
    """Assign rescue vehicles to incidents based on closest station in travel-time cost"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 5: Multi-Vehicle Rescue Dispatch")
    logger.info("=" * 70)
    
    for request_idx, incident_node in enumerate(rescue_requests, 1):
        u_data = G.nodes[incident_node]
        logger.info(f"\n📍 Incident {request_idx}: Node {incident_node} at ({u_data['lat']:.5f}, {u_data['lon']:.5f})")
        
        best_station = None
        best_route = []
        best_cost = float('inf')
        
        for station in facilities["rescue_stations"]:
            route, cost = find_safest_route(G, station["node"], incident_node)
            if cost < best_cost:
                best_cost = cost
                best_route = route
                best_station = station
        
        if best_station and best_route:
            logger.info(f"  ✓ Dispatch: {best_station['name']} (Station {best_station['id']})")
            logger.info(f"  Route has {len(best_route)-1} segments.")
            logger.info(f"  ETA: {best_cost/60:.1f} minutes")
        else:
            logger.warning("  ❌ No reachable rescue station found for this incident!")


def find_nearest_safe_zones(G: nx.DiGraph, facilities: Dict, incident_node: int) -> None:
    """Recommend and pathfind to the nearest shelters from an incident node"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 6: Evacuation Route Planning")
    logger.info("=" * 70)
    
    u_data = G.nodes[incident_node]
    logger.info(f"\n🏠 From incident at Node {incident_node} ({u_data['lat']:.5f}, {u_data['lon']:.5f})")
    
    nearby_shelters = []
    for shelter in facilities["shelters"]:
        route, cost = find_safest_route(G, incident_node, shelter["node"])
        if route:
            nearby_shelters.append((shelter, route, cost))
    
    nearby_shelters.sort(key=lambda x: x[2])
    
    if not nearby_shelters:
        logger.warning("❌ No reachable evacuation shelters found!")
        return
        
    for i, (shelter, route, cost) in enumerate(nearby_shelters[:3], 1):
        eta_min = cost / 60
        logger.info(f"  {i}. {shelter['name']} (capacity: {shelter['capacity']})")
        logger.info(f"     ETA: {eta_min:.1f} min | Route has {len(route)-1} segments.")


def export_to_geojson(
    G: nx.DiGraph,
    route_before: List[int],
    route_after: List[int],
    route_shelter: List[int],
    flood_polygon: List[Tuple[float, float]],
    facilities: Dict,
    incident_coords: Tuple[float, float],
    incident_event: Dict,
    filename: str = "disaster_scene.geojson"
) -> None:
    """
    Export all simulation layers to a React Leaflet compatible GeoJSON file.
    Note: GeoJSON coordinates are in [longitude, latitude] format.
    """
    import json
    logger.info(f"Exporting React Leaflet compatible GeoJSON features to '{filename}'...")
    
    features = []
    
    # 1. Flood Zone Polygon (shaded blue translucent)
    if flood_polygon:
        # Flip coordinates from (lat, lon) to [lon, lat]
        polygon_coords = [[ [pt[1], pt[0]] for pt in flood_polygon ]]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": polygon_coords
            },
            "properties": {
                "name": "Sentinel-1 Flood Zone",
                "type": "flood_zone",
                "fill": "#0000FF",
                "fill_opacity": 0.4,
                "stroke": "#0000FF",
                "stroke_width": 2
            }
        })
        
    # 2. Safe Conditions Route (Green LineString)
    if route_before:
        gps_path = route_to_gps_path(G, route_before)
        line_coords = [ [pt[1], pt[0]] for pt in gps_path ]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": line_coords
            },
            "properties": {
                "name": "Safe Conditions Route",
                "type": "route_before",
                "color": "#28a745",
                "width": 5,
                "opacity": 0.8
            }
        })
        
    # 3. Recalculated Detour Route (Blue LineString)
    if route_after:
        gps_path = route_to_gps_path(G, route_after)
        line_coords = [ [pt[1], pt[0]] for pt in gps_path ]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": line_coords
            },
            "properties": {
                "name": "Alternative Route (Detour)",
                "type": "route_after",
                "color": "#007bff",
                "width": 6,
                "opacity": 0.9,
                "dashArray": "5, 5"
            }
        })
        
    # 4. Detour to Shelter Route (Purple LineString)
    if route_shelter:
        gps_path = route_to_gps_path(G, route_shelter)
        line_coords = [ [pt[1], pt[0]] for pt in gps_path ]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": line_coords
            },
            "properties": {
                "name": "Station to Shelter Bypass",
                "type": "route_shelter",
                "color": "#6f42c1",
                "width": 5,
                "opacity": 0.8
            }
        })
        
    # 5. Incident Marker Point
    if incident_coords:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [incident_coords[1], incident_coords[0]]
            },
            "properties": {
                "name": f"Incident: {incident_event.get('type')}",
                "type": "incident",
                "severity": incident_event.get("severity"),
                "source": incident_event.get("source"),
                "color": "#dc3545",
                "icon": "exclamation-triangle"
            }
        })
        
    # 6. Rescue Stations Markers
    for station in facilities.get("rescue_stations", []):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [station["lon"], station["lat"]]
            },
            "properties": {
                "name": station["name"],
                "type": "rescue_station",
                "color": "#fd7e14",
                "icon": "shield-alt"
            }
        })
        
    # 7. Hospitals Markers
    for hosp in facilities.get("hospitals", []):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [hosp["lon"], hosp["lat"]]
            },
            "properties": {
                "name": hosp["name"],
                "type": "hospital",
                "capacity": hosp.get("capacity"),
                "color": "#e23e57",
                "icon": "plus-circle"
            }
        })
        
    # 8. Shelters Markers
    for shelter in facilities.get("shelters", []):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [shelter["lon"], shelter["lat"]]
            },
            "properties": {
                "name": shelter["name"],
                "type": "shelter",
                "capacity": shelter.get("capacity"),
                "color": "#28a745",
                "icon": "home"
            }
        })
        
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)
    logger.info(f"✓ Saved disaster scene GeoJSON layers to '{filename}' ready for React Leaflet frontend!")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logger.info("\n")
    logger.info("╔" + "=" * 68 + "╗")
    logger.info("║" + " " * 68 + "║")
    logger.info("║" + " SAHYADRI DISASTER ROUTING SYSTEM — REAL OSM DEMO ".center(68) + "║")
    logger.info("║" + " Dynamic Navigation on Live OpenStreetMap Data ".center(68) + "║")
    logger.info("║" + " " * 68 + "║")
    logger.info("╚" + "=" * 68 + "╝")
    
    # ------------------------------------------------------------------------
    # STEP 1: Load road network from OpenStreetMap
    # ------------------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("STEP 1: Loading Real OpenStreetMap Road Network")
    logger.info("=" * 70)
    
    place_name = "Mangaluru, Karnataka, India"
    logger.info(f"Downloading road network for '{place_name}'...")
    
    start_time = time.time()
    loader = OSMLoader()
    osm_data = loader.load_from_place(place_name)
    
    if not osm_data.get("nodes"):
        logger.error("Failed to load road network from OpenStreetMap. Please check your internet connection.")
        sys.exit(1)
        
    extractor = RoadExtractor()
    edges = extractor.extract(osm_data)
    
    builder = GraphBuilder()
    G_di = builder.build(edges, osm_data["nodes"])
    
    # Enable bidirectional traversal (DiGraph is already returned with reverse edges if oneway=False)
    logger.info(f"✓ Network loaded in {time.time() - start_time:.2f} seconds")
    logger.info(f"✓ Graph contains: {G_di.number_of_nodes()} junctions, {G_di.number_of_edges()} road segments")
    
    # Calculate center latitude and longitude dynamically from the loaded nodes
    lats = [node["lat"] for node in osm_data["nodes"].values()]
    lons = [node["lon"] for node in osm_data["nodes"].values()]
    mangaluru_lat = sum(lats) / len(lats)
    mangaluru_lon = sum(lons) / len(lons)
    
    logger.info("STEP 2: Querying and Mapping Facilities from OpenStreetMap")
    logger.info("=" * 70)
    
    mapper = NodeMapper(G_di)
    
    # 1. Query real hospitals from OSM data
    logger.info("Extracting healthcare facilities from OSM data...")
    hosp_extractor = HospitalExtractor(include_clinics=True)
    osm_hospitals = hosp_extractor.extract(osm_data)
    
    hospitals = []
    for hosp in osm_hospitals:
        if hosp.get("lat") and hosp.get("lon"):
            node = mapper.nearest_node(hosp["lat"], hosp["lon"])
            if node:
                hospitals.append({
                    "id": str(hosp["osm_id"]),
                    "name": hosp.get("name") or f"Hospital ({hosp['osm_id']})",
                    "node": node,
                    "lat": hosp["lat"],
                    "lon": hosp["lon"],
                    "capacity": hosp.get("beds") or 100
                })
                logger.info(f"✓ Extracted and mapped Hospital: {hosp.get('name') or 'Unnamed'} (OSM Node {node})")
                
    # Fallback if no hospitals found
    if not hospitals:
        logger.info("⚠️ No hospitals found in the downloaded OSM data. Adding a fallback.")
        fallback_coords = (mangaluru_lat + 0.005, mangaluru_lon + 0.005)
        node = mapper.nearest_node(*fallback_coords)
        hospitals.append({
            "id": "H1-fallback",
            "name": "Central Hospital (Fallback)",
            "node": node,
            "lat": fallback_coords[0],
            "lon": fallback_coords[1],
            "capacity": 250
        })
        logger.info(f"✓ Mapped Fallback Hospital to OSM Node {node}")
        
    # 2. Query real shelters from OSM data
    logger.info("Extracting shelters and community assembly points from OSM data...")
    shelter_mapper = ShelterMapper(mapper, include_schools_as_shelters=True)
    osm_shelters = shelter_mapper.extract_from_osm(osm_data)
    
    shelters = []
    for s in osm_shelters:
        shelters.append({
            "id": str(s["osm_id"]),
            "name": s.get("name") or f"Shelter ({s['osm_id']})",
            "node": s["nearest_node"],
            "lat": s["lat"],
            "lon": s["lon"],
            "capacity": s.get("capacity") or 300
        })
        logger.info(f"✓ Extracted and snapped Shelter: {s.get('name') or 'Unnamed'} (OSM Node {s['nearest_node']})")
        
    # Fallback if no shelters found
    if not shelters:
        logger.info("⚠️ No shelters found in the downloaded OSM data. Adding fallbacks.")
        fallback_s1 = (mangaluru_lat + 0.003, mangaluru_lon - 0.003)
        fallback_s2 = (mangaluru_lat - 0.004, mangaluru_lon + 0.004)
        node1 = mapper.nearest_node(*fallback_s1)
        node2 = mapper.nearest_node(*fallback_s2)
        shelters.append({
            "id": "S1-fallback",
            "name": "Community Center (Fallback)",
            "node": node1,
            "lat": fallback_s1[0],
            "lon": fallback_s1[1],
            "capacity": 500
        })
        shelters.append({
            "id": "S2-fallback",
            "name": "School Shelter (Fallback)",
            "node": node2,
            "lat": fallback_s2[0],
            "lon": fallback_s2[1],
            "capacity": 300
        })
        logger.info(f"✓ Mapped Fallback Shelters to OSM Nodes {node1} and {node2}")
        
    # 3. Query real rescue stations from OSM data
    logger.info("Extracting rescue stations (fire stations / ambulance stations) from OSM data...")
    rescue_stations = []
    
    # Scan nodes
    for node_id, node in osm_data.get("nodes", {}).items():
        tags = node.get("tags", {})
        if tags.get("amenity") == "fire_station" or tags.get("emergency") == "ambulance_station":
            node_idx = mapper.nearest_node(node["lat"], node["lon"])
            if node_idx:
                rescue_stations.append({
                    "id": str(node_id),
                    "name": tags.get("name") or f"Rescue Station ({node_id})",
                    "node": node_idx,
                    "lat": node["lat"],
                    "lon": node["lon"]
                })
                logger.info(f"✓ Extracted and snapped Rescue Station: {tags.get('name') or 'Unnamed'} (OSM Node {node_idx})")
                
    # Scan ways (polygons)
    for way_id, way in osm_data.get("ways", {}).items():
        tags = way.get("tags", {})
        if tags.get("amenity") == "fire_station" or tags.get("emergency") == "ambulance_station":
            # calculate centroid
            nodes_dict = osm_data.get("nodes", {})
            way_nodes = way.get("nodes", [])
            valid_nodes = [nodes_dict[nid] for nid in way_nodes if nid in nodes_dict]
            if valid_nodes:
                lat = sum(n["lat"] for n in valid_nodes) / len(valid_nodes)
                lon = sum(n["lon"] for n in valid_nodes) / len(valid_nodes)
                node_idx = mapper.nearest_node(lat, lon)
                if node_idx:
                    rescue_stations.append({
                        "id": str(way_id),
                        "name": tags.get("name") or f"Rescue Station ({way_id})",
                        "node": node_idx,
                        "lat": lat,
                        "lon": lon
                    })
                    logger.info(f"✓ Extracted and snapped Rescue Station Way: {tags.get('name') or 'Unnamed'} (OSM Node {node_idx})")
                    
    # Fallback if no rescue stations found
    if not rescue_stations:
        logger.info("⚠️ No rescue stations found in downloaded OSM data. Adding a fallback.")
        station_coords = (mangaluru_lat - 0.002, mangaluru_lon - 0.002)
        station_node = mapper.nearest_node(*station_coords)
        rescue_stations.append({
            "id": "RS1-fallback",
            "name": "Station A (Fallback)",
            "node": station_node,
            "lat": station_coords[0],
            "lon": station_coords[1]
        })
        logger.info(f"✓ Mapped Fallback Rescue Station to OSM Node {station_node}")
    
    facilities = {
        "hospitals": hospitals,
        "shelters": shelters,
        "rescue_stations": rescue_stations
    }
    
    # Choose our start and query the dynamic incident from the emergency feed
    start_node = facilities["rescue_stations"][0]["node"]
    
    feed = EmergencyFeed()
    incident_event = feed.get_latest_incident(mangaluru_lat, mangaluru_lon)
    incident_coords = (incident_event["lat"], incident_event["lon"])
    incident_node = mapper.nearest_node(*incident_coords)
    
    logger.info(f"\n🚑 Start/Rescue Station Node: {start_node}")
    logger.info(f"📍 Evacuation/Incident Node: {incident_node} at {incident_coords} (Type: '{incident_event['type']}')")
    
    # ------------------------------------------------------------------------
    # STEP 3: Initial Routing (Safe Conditions)
    # ------------------------------------------------------------------------
    logger.info("\n" + "=" * 70)
    logger.info("STEP 3: Initial Routing (Safe Conditions)")
    logger.info("=" * 70)
    
    route_before, cost_before = find_safest_route(G_di, start_node, incident_node)
    
    if route_before:
        logger.info("\n✅ Safe Conditions Route:")
        print_route_details(route_before, G_di, cost_before)
    else:
        logger.error("❌ No route found even in safe conditions! Make sure graph is fully connected.")
        sys.exit(1)
        
    # ------------------------------------------------------------------------
    # STEP 4: Weather Ingestion & Localized Flood Simulation
    # ------------------------------------------------------------------------
    logger.info("\n" + "=" * 70)
    logger.info("STEP 4: Weather Ingestion & Localized Flood Simulation")
    logger.info("=" * 70)

    # Load env and fetch current weather
    env = load_env()
    api_key = env.get("open_weather_api")
    
    # Use the dynamically calculated map center for the weather coordinates
    
    weather_data = None
    if api_key:
        logger.info(f"Connecting to OpenWeather API for coordinates: ({mangaluru_lat}, {mangaluru_lon})...")
        try:
            weather_data = get_openweather_current(mangaluru_lat, mangaluru_lon, api_key)
            logger.info("✓ Successfully fetched live weather data from OpenWeather.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch live weather: {e}. Falling back to simulated monsoon state.")
    else:
        logger.warning("⚠️ No 'open_weather_api' key found in .env. Falling back to simulated monsoon state.")
        
    # Weather variables with realistic heavy monsoon simulation as fallback
    if weather_data:
        temp = weather_data.get("temperature_c") or 28.0
        humidity = weather_data.get("humidity_pct") or 85.0
        wind_speed = weather_data.get("wind_speed_ms") or 5.5
        rain_1h = weather_data.get("rain_1h_mm") or 0.0
        weather_desc = weather_data.get("weather_description") or "scattered clouds"
    else:
        temp = 27.5
        humidity = 92.0
        wind_speed = 8.5
        rain_1h = 12.5  # Simulate heavy rain in mm/h
        weather_desc = "heavy intensity rain (simulated monsoon)"

    logger.info(f"\n🌤️ Current Weather Metrics for Mangaluru:")
    logger.info(f"   Description: {weather_desc.capitalize()}")
    logger.info(f"   Temperature: {temp}°C")
    logger.info(f"   Humidity:    {humidity}%")
    logger.info(f"   Wind Speed:  {wind_speed} m/s")
    logger.info(f"   Rainfall:    {rain_1h} mm/h")

    # Predict & scale waterlogging buffer distance based on rainfall
    # Base buffer: 200m. Every 1mm of rainfall increases buffer by 15m (up to 500m max).
    buffer_distance_m = 200.0
    if rain_1h > 0:
        buffer_distance_m = min(500.0, 200.0 + (rain_1h * 15.0))
        logger.info(f"🌧️ Active rainfall detected! Dynamically scaling waterlogging buffer: {buffer_distance_m:.1f}m (base: 200m)")
    else:
        logger.info(f"🌤️ No active rainfall. Using baseline waterlogging buffer: {buffer_distance_m:.1f}m")

    # Instantiate Sentinel-1 satellite loader and extract the segmented flood polygon dynamically
    sentinel_loader = SentinelFloodLoader()
    flood_polygon = sentinel_loader.get_latest_flood_polygon(mangaluru_lat, mangaluru_lon)
    
    logger.info("\n🌊 Tracing Sentinel-1 satellite flood extent polygon from dynamic segmentation...")
    logger.info(f"   Vertices: {flood_polygon}")
    
    blocked, slowed = apply_dynamic_risk_model(G_di, flood_polygon, rain_1h, mangaluru_lat, mangaluru_lon, buffer_distance_m=buffer_distance_m)
    
    # Print distinct blocked roads
    blocked_names = sorted(list(set([name for _, _, name in blocked])))
    slowed_names = sorted(list(set([name for _, _, name in slowed if name not in blocked_names])))
    
    logger.info(f"🚫 Blocked roads intersecting satellite flood polygon: {', '.join(blocked_names) if blocked_names else 'None'}")
    logger.info(f"⚠️ Slow zones near flood polygon: {', '.join(slowed_names) if slowed_names else 'None'}")
    
    logger.info(f"\n🗺️ Recalculating route around flood zone...")
    route_after, cost_after = find_safest_route(G_di, start_node, incident_node)
    
    if route_after:
        logger.info("\n✅ Alternative Route (After Flood):")
        print_route_details(route_after, G_di, cost_after)
        
        time_increase = ((cost_after - cost_before) / cost_before) * 100
        logger.info(f"\n📊 Route Analysis:")
        logger.info(f"   Before flood: {cost_before:.1f}s ({cost_before/60:.1f} min)")
        logger.info(f"   After flood:  {cost_after:.1f}s ({cost_after/60:.1f} min)")
        logger.info(f"   Increase:     {time_increase:.1f}%")
    else:
        logger.warning("\n❌ No route available! Incident node is completely isolated inside the flood polygon.")
        
    # Highlight routing by calculating a route from the station to a safe shelter outside the flood zone
    route_shelter = []
    if facilities["shelters"]:
        target_shelter = facilities["shelters"][0]
        shelter_node = target_shelter["node"]
        logger.info(f"\n🗺️ Dispatching station vehicle to shelter '{target_shelter['name']}' (Node {shelter_node}) bypassing flood...")
        route_shelter, cost_shelter = find_safest_route(G_di, start_node, shelter_node)
        if route_shelter:
            logger.info("✅ Detour Route to Shelter found:")
            print_route_details(route_shelter, G_di, cost_shelter)
        else:
            logger.warning("❌ No route to shelter available!")
        
    # ------------------------------------------------------------------------
    # STEP 5: Multi-vehicle dispatch
    # ------------------------------------------------------------------------
    dispatch_rescue_fleet(G_di, facilities, [incident_node])
    
    # ------------------------------------------------------------------------
    # STEP 6: Evacuation planning
    # ------------------------------------------------------------------------
    find_nearest_safe_zones(G_di, facilities, incident_node)
    
    # Export results to React Leaflet compatible GeoJSON
    export_to_geojson(
        G=G_di,
        route_before=route_before,
        route_after=route_after,
        route_shelter=route_shelter,
        flood_polygon=flood_polygon,
        facilities=facilities,
        incident_coords=incident_coords,
        incident_event=incident_event,
        filename="disaster_scene.geojson"
    )
    
    logger.info("\n" + "=" * 70)
    logger.info("DEMO SUMMARY")
    logger.info("=" * 70)
    logger.info("\n✓ Successfully verified integration with actual OpenStreetMap data.")
    logger.info("✓ Mapped real-world coordinates to graph nodes dynamically.")
    logger.info("✓ Evaluated and avoided simulated localized flood zones.")
    logger.info("✓ Exported React Leaflet GeoJSON layer output to 'disaster_scene.geojson'.")
    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
        logger.info("\n✅ OSM Demo completed successfully!\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ OSM Demo failed: {e}", exc_info=True)
        sys.exit(1)
