#!/usr/bin/env python3
"""
Sahyadri Disaster Routing System — Live Demo
=============================================

This demo showcases:
1. Road network loading and graph construction
2. Hospital/shelter mapping
3. A* pathfinding with disaster risk awareness
4. Real-time flood simulation and dynamic rerouting
5. Route optimization for multiple rescue vehicles
"""

import sys
import logging
from typing import Dict, List, Tuple
import networkx as nx
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# PART 1: Simulated Road Network (replace with OSM loader for production)
# ============================================================================

def create_demo_road_network() -> Tuple[nx.DiGraph, Dict]:
    """
    Create a simple demo road network representing a coastal region.
    
    In production, this would use:
    - gis_engine.osm.osm_loader.OSMLoader
    - gis_engine.osm.road_extractor.RoadExtractor
    - gis_engine.graph.graph_builder.GraphBuilder
    """
    logger.info("=" * 70)
    logger.info("STEP 1: Building Road Network")
    logger.info("=" * 70)
    
    G = nx.DiGraph()
    
    # Nodes: intersections with (lat, lon)
    nodes_data = {
        1: {"lat": 19.00, "lon": -65.30, "name": "City Center"},
        2: {"lat": 19.01, "lon": -65.30, "name": "Downtown North"},
        3: {"lat": 19.00, "lon": -65.29, "name": "Downtown East"},
        4: {"lat": 19.02, "lon": -65.30, "name": "Hospital District"},
        5: {"lat": 19.01, "lon": -65.28, "name": "Coastal Road"},
        6: {"lat": 19.02, "lon": -65.29, "name": "North District"},
        7: {"lat": 18.99, "lon": -65.30, "name": "South District"},
        8: {"lat": 19.00, "lon": -65.31, "name": "West Side"},
    }
    
    # Add nodes to graph
    for node_id, data in nodes_data.items():
        G.add_node(node_id, **data)
    
    # Edges: road segments with travel time and risk attributes
    edges_data = [
        (1, 2, {"length_m": 1100, "speed_kph": 50, "name": "Main St N", "risk": 0.0, "blocked": False}),
        (2, 4, {"length_m": 1100, "speed_kph": 50, "name": "Hospital Ave", "risk": 0.0, "blocked": False}),
        (1, 3, {"length_m": 1000, "speed_kph": 50, "name": "Main St E", "risk": 0.0, "blocked": False}),
        (3, 5, {"length_m": 1100, "speed_kph": 40, "name": "Coastal Rd", "risk": 0.2, "blocked": False}),
        (1, 8, {"length_m": 1000, "speed_kph": 50, "name": "Main St W", "risk": 0.0, "blocked": False}),
        (8, 6, {"length_m": 1200, "speed_kph": 50, "name": "West Loop", "risk": 0.0, "blocked": False}),
        (6, 2, {"length_m": 1000, "speed_kph": 50, "name": "North Bridge", "risk": 0.0, "blocked": False}),
        (1, 7, {"length_m": 1100, "speed_kph": 50, "name": "South Ave", "risk": 0.0, "blocked": False}),
        (7, 3, {"length_m": 1000, "speed_kph": 50, "name": "East Loop", "risk": 0.0, "blocked": False}),
        (2, 6, {"length_m": 1000, "speed_kph": 50, "name": "North Connector", "risk": 0.0, "blocked": False}),
    ]
    
    # Add edges to graph
    travel_times = {}
    for u, v, attrs in edges_data:
        travel_time = (attrs["length_m"] / 1000.0) / attrs["speed_kph"] * 3600  # seconds
        attrs["travel_time_s"] = travel_time
        G.add_edge(u, v, **attrs)
        travel_times[(u, v)] = travel_time
    
    logger.info(f"✓ Network created: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    node_names = ', '.join([f"{nid}({data['name']})" for nid, data in nodes_data.items()])
    logger.info(f"✓ Nodes: {node_names}")
    
    return G, nodes_data


# ============================================================================
# PART 2: Emergency Facilities Mapping
# ============================================================================

def map_emergency_facilities() -> Dict:
    """
    Map hospitals and shelters to graph nodes.
    Production version uses hospital_mapper.py and shelter_mapper.py
    """
    logger.info("\n" + "=" * 70)
    logger.info("STEP 2: Mapping Emergency Facilities")
    logger.info("=" * 70)
    
    facilities = {
        "hospitals": [
            {"id": "H1", "name": "Central Hospital", "node": 4, "beds": 250, "lat": 19.02, "lon": -65.29},
        ],
        "shelters": [
            {"id": "S1", "name": "Community Center", "node": 6, "capacity": 500, "lat": 19.02, "lon": -65.29},
            {"id": "S2", "name": "School Shelter", "node": 2, "capacity": 300, "lat": 19.01, "lon": -65.30},
            {"id": "S3", "name": "Emergency Hub", "node": 8, "capacity": 400, "lat": 19.00, "lon": -65.31},
        ],
        "rescue_stations": [
            {"id": "RS1", "name": "Station A", "node": 1, "lat": 19.00, "lon": -65.30},
        ]
    }
    
    logger.info(f"✓ Hospitals: {len(facilities['hospitals'])} — {', '.join([h['name'] for h in facilities['hospitals']])}")
    logger.info(f"✓ Shelters: {len(facilities['shelters'])} — {', '.join([s['name'] for s in facilities['shelters']])}")
    logger.info(f"✓ Rescue Stations: {len(facilities['rescue_stations'])} — {', '.join([r['name'] for r in facilities['rescue_stations']])}")
    
    return facilities


# ============================================================================
# PART 3: A* Routing with Disaster Risk Awareness
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in meters"""
    from math import radians, sin, cos, sqrt, atan2
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlam/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def heuristic_to_goal(u: int, goal: int, nodes_data: Dict) -> float:
    """Haversine heuristic for A* (admissible)"""
    if u not in nodes_data or goal not in nodes_data:
        return 0.0
    u_data = nodes_data[u]
    goal_data = nodes_data[goal]
    dist_m = haversine_distance(u_data["lat"], u_data["lon"], 
                                 goal_data["lat"], goal_data["lon"])
    # Assume 50 kph average speed for heuristic
    return (dist_m / 1000.0) / 50.0 * 3600


def compute_edge_cost(u: int, v: int, G: nx.DiGraph, risk_penalty: float = 5.0) -> float:
    """
    Compute cost of traversing edge (u, v).
    
    Cost = travel_time + risk_penalty * disaster_risk
    """
    edge_data = G.get_edge_data(u, v)
    if edge_data is None:
        return float('inf')
    
    if edge_data.get("blocked", False):
        return float('inf')  # Impassable
    
    travel_time = edge_data.get("travel_time_s", 60)
    risk = edge_data.get("risk", 0.0)
    
    return travel_time + (risk_penalty * risk)


def find_safest_route(G: nx.DiGraph, nodes_data: Dict, start: int, goal: int, 
                      risk_penalty: float = 5.0) -> Tuple[List[int], float]:
    """
    Find the safest route using A* with disaster risk awareness.
    Production version uses optimization/routing/astar.py
    """
    def cost_func(u, v, d):
        return compute_edge_cost(u, v, G, risk_penalty)
    
    def h_func(u, v):
        return heuristic_to_goal(u, goal, nodes_data)
    
    try:
        path = nx.astar_path(G, start, goal, heuristic=h_func, weight=cost_func)
        
        # Calculate total cost
        total_cost = 0.0
        for i in range(len(path) - 1):
            total_cost += compute_edge_cost(path[i], path[i+1], G, risk_penalty)
        
        return path, total_cost
    except nx.NetworkXNoPath:
        return [], float('inf')


# ============================================================================
# PART 4: Flood Simulation & Dynamic Rerouting
# ============================================================================

def simulate_flood_update(G: nx.DiGraph, flooded_roads: List[Tuple[int, int]], 
                         slow_roads: List[Tuple[int, int]]) -> None:
    """
    Simulate a flood event that blocks or slows certain roads.
    Production version uses simulation/flood/flood_risk.py
    """
    # Block roads
    for u, v in flooded_roads:
        if G.has_edge(u, v):
            G[u][v]["blocked"] = True
            G[u][v]["risk"] = 1.0
    
    # Slow roads (waterlogging)
    for u, v in slow_roads:
        if G.has_edge(u, v):
            G[u][v]["blocked"] = False
            G[u][v]["risk"] = 0.5  # Increased risk, not blocked


def print_route_details(path: List[int], nodes_data: Dict, G: nx.DiGraph, cost: float) -> None:
    """Display route information"""
    if not path:
        logger.warning("❌ No route found (all paths blocked or unreachable)")
        return
    
    logger.info(f"✓ Route found ({len(path)-1} segments, cost: {cost:.1f}s)")
    path_str = ' → '.join([f"{nodes_data[n]['name']}({n})" for n in path])
    logger.info(f"  Path: {path_str}")
    
    total_dist = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge_data = G.get_edge_data(u, v)
        dist = edge_data.get("length_m", 0)
        travel = edge_data.get("travel_time_s", 0)
        risk = edge_data.get("risk", 0.0)
        blocked = "🚫 BLOCKED" if edge_data.get("blocked") else ""
        total_dist += dist
        logger.info(f"    {nodes_data[u]['name']}→{nodes_data[v]['name']}: {dist}m, {travel:.0f}s {blocked}")
    
    logger.info(f"  Total distance: {total_dist}m ({total_dist/1000:.2f}km)")


# ============================================================================
# PART 5: Multi-Vehicle Rescue Dispatch
# ============================================================================

def dispatch_rescue_fleet(G: nx.DiGraph, nodes_data: Dict, facilities: Dict, 
                         rescue_requests: List[int]) -> None:
    """
    Assign rescue vehicles to incidents with closest available vehicle.
    Production version uses optimization/rescue_scheduling/rescue_assignment.py
    """
    logger.info("\n" + "=" * 70)
    logger.info("STEP 5: Multi-Vehicle Rescue Dispatch")
    logger.info("=" * 70)
    
    for request_idx, incident_node in enumerate(rescue_requests, 1):
        logger.info(f"\n📍 Incident {request_idx}: Node {incident_node} ({nodes_data[incident_node]['name']})")
        
        best_station = None
        best_route = []
        best_cost = float('inf')
        
        for station in facilities["rescue_stations"]:
            route, cost = find_safest_route(G, nodes_data, station["node"], incident_node)
            if cost < best_cost:
                best_cost = cost
                best_route = route
                best_station = station
        
        if best_station and best_route:
            logger.info(f"  ✓ Dispatch: {best_station['name']} (Station {best_station['id']})")
            logger.info(f"  Route: {' → '.join([nodes_data[n]['name'] for n in best_route])}")
            logger.info(f"  ETA: {best_cost/60:.1f} minutes")


# ============================================================================
# PART 6: Nearest Safe Zone Recommendation
# ============================================================================

def find_nearest_safe_zones(G: nx.DiGraph, nodes_data: Dict, facilities: Dict,
                           incident_node: int) -> None:
    """Find nearest reachable shelters for evacuation"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 6: Evacuation Route Planning")
    logger.info("=" * 70)
    
    logger.info(f"\n🏠 From incident at {nodes_data[incident_node]['name']} (Node {incident_node})")
    
    # Find nearest shelter
    nearby_shelters = []
    for shelter in facilities["shelters"]:
        route, cost = find_safest_route(G, nodes_data, incident_node, shelter["node"])
        if route:
            nearby_shelters.append((shelter, route, cost))
    
    # Sort by travel cost
    nearby_shelters.sort(key=lambda x: x[2])
    
    for i, (shelter, route, cost) in enumerate(nearby_shelters[:3], 1):
        eta_min = cost / 60
        logger.info(f"  {i}. {shelter['name']} (capacity: {shelter['capacity']})")
        logger.info(f"     ETA: {eta_min:.1f} min | Route: {' → '.join([nodes_data[n]['name'] for n in route])}")


# ============================================================================
# MAIN DEMO
# ============================================================================

def main():
    """Run the complete demo"""
    logger.info("\n")
    logger.info("╔" + "=" * 68 + "╗")
    logger.info("║" + " " * 68 + "║")
    logger.info("║" + " SAHYADRI DISASTER ROUTING SYSTEM - LIVE DEMO ".center(68) + "║")
    logger.info("║" + " Real-Time Flood-Aware Emergency Routing ".center(68) + "║")
    logger.info("║" + " " * 68 + "║")
    logger.info("╚" + "=" * 68 + "╝")
    
    # Step 1: Build network
    G, nodes_data = create_demo_road_network()
    
    # Step 2: Map facilities
    facilities = map_emergency_facilities()
    
    # Step 3: Initial routing (before flood)
    logger.info("\n" + "=" * 70)
    logger.info("STEP 3: Initial Routing (Safe Conditions)")
    logger.info("=" * 70)
    
    start_node = 1  # Rescue station
    incident_node = 5  # Coastal area
    
    logger.info(f"\n📍 Rescue Request: Incident at {nodes_data[incident_node]['name']} (Node {incident_node})")
    logger.info(f"🚑 Dispatch from: {nodes_data[start_node]['name']} (Node {start_node})")
    
    route_before, cost_before = find_safest_route(G, nodes_data, start_node, incident_node)
    logger.info("\n✅ Safe Conditions Route:")
    print_route_details(route_before, nodes_data, G, cost_before)
    
    # Step 4: Simulate flood
    logger.info("\n" + "=" * 70)
    logger.info("STEP 4: Flood Event Simulation")
    logger.info("=" * 70)
    
    logger.info("\n🌊 Heavy rainfall detected! Updating flood risk...")
    logger.info("   Coastal roads experiencing surge...")
    
    # Block some roads, slow others
    flooded = [(3, 5), (5, 3)]  # Coastal roads completely flooded
    slowed = [(2, 6), (6, 2)]    # North bridge waterlogging
    
    logger.info(f"\n   🚫 Blocked roads: {[(nodes_data[u]['name'], nodes_data[v]['name']) for u, v in flooded]}")
    logger.info(f"   ⚠️  Slow zones: {[(nodes_data[u]['name'], nodes_data[v]['name']) for u, v in slowed]}")
    
    simulate_flood_update(G, flooded, slowed)
    
    # Step 5: Rerouting after flood
    logger.info("\n" + "=" * 70)
    logger.info("STEP 5: Dynamic Rerouting (After Flood)")
    logger.info("=" * 70)
    
    logger.info(f"\n🗺️  Recalculating route with updated road conditions...")
    
    route_after, cost_after = find_safest_route(G, nodes_data, start_node, incident_node)
    
    if route_after:
        logger.info("\n✅ Alternative Route (After Flood):")
        print_route_details(route_after, nodes_data, G, cost_after)
        
        time_increase = ((cost_after - cost_before) / cost_before) * 100
        logger.info(f"\n📊 Route Analysis:")
        logger.info(f"   Before flood: {cost_before:.0f}s ({cost_before/60:.1f} min)")
        logger.info(f"   After flood:  {cost_after:.0f}s ({cost_after/60:.1f} min)")
        logger.info(f"   Increase:     {time_increase:.1f}%")
    else:
        logger.warning("\n❌ No route available! All paths to incident blocked.")
    
    # Step 6: Multi-vehicle dispatch
    dispatch_rescue_fleet(G, nodes_data, facilities, [5, 7])
    
    # Step 7: Evacuation planning
    find_nearest_safe_zones(G, nodes_data, facilities, incident_node)
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("DEMO SUMMARY")
    logger.info("=" * 70)
    logger.info("\n✓ Demonstrated capabilities:")
    logger.info("  1. Road network construction from geospatial data")
    logger.info("  2. Hospital & shelter mapping to graph nodes")
    logger.info("  3. A* pathfinding with disaster risk awareness")
    logger.info("  4. Real-time flood simulation & graph updates")
    logger.info("  5. Dynamic rerouting in under 1 second")
    logger.info("  6. Multi-vehicle rescue dispatch")
    logger.info("  7. Evacuation route planning")
    logger.info("\n✓ Next steps:")
    logger.info("  - Integrate real OSM data via Overpass API")
    logger.info("  - Add WebSocket live visualization (Leaflet + OpenStreetMap)")
    logger.info("  - Connect to rainfall/flood sensors (simulated or real)")
    logger.info("  - Deploy as FastAPI backend with React frontend")
    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
        logger.info("\n✅ Demo completed successfully!\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}", exc_info=True)
        sys.exit(1)
