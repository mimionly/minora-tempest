"""
Core routing engine.
Handles map loading (in-memory graph), flood updates, shortest-path routing,
and name-based search over named locations/roads only.
"""

import time
import math
import networkx as nx


class FloodRoutingEngine:
    def __init__(self):
        self.graph = nx.Graph()
        self.flooded_edges = {}  # (u, v) -> severity level

    # ------------------------------------------------------------------
    # MAP LOADING
    # ------------------------------------------------------------------

    def load_demo_graph(self):
        nodes = {
            "kadri_fire_station": (12.8916, 74.8447),
            "balmatta":           (12.8756, 74.8420),
            "car_street":         (12.8697, 74.8370),
            "bunder":              (12.8642, 74.8340),
            "kudla":               (12.8700, 74.8300),
            "bejai":                (12.8830, 74.8500),
            "surathkal":            (13.0100, 74.7940),
            "state_bank":           (12.8730, 74.8430),
        }

        edges = [
            ("kadri_fire_station", "balmatta", "Kadri Hills Road"),
            ("balmatta", "car_street", "Balmatta Road"),
            ("car_street", "bunder", "Car Street"),
            ("bunder", "kudla", "Bunder Road"),
            ("balmatta", "state_bank", "Lighthouse Hill Road"),
            ("state_bank", "car_street", "Bank Junction Road"),
            ("kadri_fire_station", "bejai", "Bejai Main Road"),
            ("bejai", "state_bank", "Bejai-Kapikad Road"),
            ("bejai", "surathkal", "NH66 Bypass"),
        ]

        for name, (lat, lon) in nodes.items():
            label = name.replace("_", " ").title()
            self.graph.add_node(name, lat=lat, lon=lon, label=label, named=True)

        for u, v, road_name in edges:
            dist_km = self._haversine(nodes[u], nodes[v])
            travel_time_min = (dist_km / 30) * 60
            self.graph.add_edge(u, v, base_weight=travel_time_min,
                                 weight=travel_time_min, distance_km=dist_km,
                                 road_name=road_name)

        return self.graph

    def load_from_osm(self, place_name: str, dist_meters: int = 10000):
        """
        Loads a REAL road network from OpenStreetMap within dist_meters of
        an address. Requires internet.
        """
        import osmnx as ox

        g = ox.graph_from_address(place_name, dist=dist_meters, network_type="drive")
        g = nx.Graph(g)

        # CRITICAL FIX: OSM node IDs load as integers (e.g. 276326020).
        # FastAPI/JSON/URLs always carry them as strings. Relabel every
        # node to a string ONCE here, so the whole system (routing,
        # search, flood updates) only ever deals with string IDs and
        # comparisons never silently fail.
        g = nx.relabel_nodes(g, {n: str(n) for n in g.nodes})

        for node, data in g.nodes(data=True):
            data["lat"] = data.pop("y")
            data["lon"] = data.pop("x")

        for u, v, data in g.edges(data=True):
            length_m = data.get("length", 100)
            travel_time_min = (length_m / 1000 / 30) * 60
            data["base_weight"] = travel_time_min
            data["weight"] = travel_time_min
            data["road_name"] = self._clean_road_name(data.get("name"))

        # Build a label per junction from the names of real roads meeting
        # there. Mark whether the junction is "named" (has at least one
        # real road name) — only named junctions are searchable/selectable
        # by the user. Unnamed junctions stay in the graph (needed as
        # pass-through points for routing) but are hidden from search.
        for node in g.nodes:
            road_names = set()
            for neighbor in g.neighbors(node):
                rn = g[node][neighbor].get("road_name")
                if rn and rn != "Unnamed Road":
                    road_names.add(rn)

            if road_names:
                g.nodes[node]["label"] = "Junction of " + " & ".join(sorted(road_names)[:2])
                g.nodes[node]["named"] = True
            else:
                g.nodes[node]["label"] = f"Unnamed Junction ({node})"
                g.nodes[node]["named"] = False

        self.graph = g
        return self.graph

    def save_graph(self, path="map_cache.graphml"):
        g_copy = self.graph.copy()
        for u, v, data in g_copy.edges(data=True):
            data.pop("geometry", None)
        nx.write_graphml(g_copy, path)

    def load_saved_graph(self, path="map_cache.graphml"):
        self.graph = nx.read_graphml(path)
        for node, data in self.graph.nodes(data=True):
            data["lat"] = float(data["lat"])
            data["lon"] = float(data["lon"])
            data["named"] = data.get("named") in (True, "True", "true")
        for u, v, data in self.graph.edges(data=True):
            data["weight"] = float(data["weight"])
            data["base_weight"] = float(data["base_weight"])
        return self.graph

    @staticmethod
    def _clean_road_name(raw_name):
        if raw_name is None:
            return "Unnamed Road"
        if isinstance(raw_name, list):
            return raw_name[0]
        return raw_name

    @staticmethod
    def _haversine(coord1, coord2):
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    # ------------------------------------------------------------------
    # SEARCH  (named locations + named roads only)
    # ------------------------------------------------------------------

    def search_locations(self, query: str, limit: int = 15):
        """
        Search junctions by name. Only returns junctions flagged 'named'
        (i.e. at least one real road name meets there) — unnamed OSM
        stub nodes are never shown to the user.
        """
        query = query.strip().lower()
        if not query:
            return []

        results = []
        for n, d in self.graph.nodes(data=True):
            if not d.get("named"):
                continue
            if query in d.get("label", "").lower():
                results.append({"id": n, "label": d["label"], "lat": d["lat"], "lon": d["lon"]})
            if len(results) >= limit:
                break
        return results

    def search_roads(self, query: str, limit: int = 15):
        """
        Search roads by name for flood reporting. Returns individual
        road segments (edges) — since a long road can have several
        segments/junctions, each match includes both endpoint IDs so
        the frontend can flood that exact segment directly.
        """
        query = query.strip().lower()
        if not query:
            return []

        results = []
        seen = set()
        for u, v, d in self.graph.edges(data=True):
            road_name = d.get("road_name", "Unnamed Road")
            if road_name == "Unnamed Road":
                continue
            if query in road_name.lower():
                key = (road_name, u, v)
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "node_a": u,
                    "node_b": v,
                    "road_name": road_name,
                    "label_a": self.graph.nodes[u].get("label", u),
                    "label_b": self.graph.nodes[v].get("label", v),
                })
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # FLOOD UPDATES
    # ------------------------------------------------------------------

    def mark_flooded(self, node_a: str, node_b: str, severity: str = "impassable"):
        node_a, node_b = str(node_a), str(node_b)

        if node_a == node_b:
            raise ValueError("A road needs two different junctions — start and end can't be the same.")

        if not self.graph.has_edge(node_a, node_b):
            raise ValueError(f"No road exists directly between {node_a} and {node_b}")

        base = self.graph[node_a][node_b]["base_weight"]
        road_name = self.graph[node_a][node_b].get("road_name", "Unnamed Road")

        if severity == "impassable":
            self.graph[node_a][node_b]["weight"] = float("inf")
            self.flooded_edges[(node_a, node_b)] = severity
        elif severity == "slow":
            self.graph[node_a][node_b]["weight"] = base * 5
            self.flooded_edges[(node_a, node_b)] = severity
        elif severity == "clear":
            self.graph[node_a][node_b]["weight"] = base
            self.flooded_edges.pop((node_a, node_b), None)
            self.flooded_edges.pop((node_b, node_a), None)
        else:
            raise ValueError("severity must be 'impassable', 'slow', or 'clear'")

        return {
            "edge": (node_a, node_b),
            "road_name": road_name,
            "severity": severity,
            "new_weight": self.graph[node_a][node_b]["weight"],
        }

    # ------------------------------------------------------------------
    # ROUTING
    # ------------------------------------------------------------------

    def get_route(self, start: str, end: str):
        start, end = str(start), str(end)

        if start not in self.graph or end not in self.graph:
            return {"error": f"Unknown junction(s): {start}, {end}"}

        t0 = time.perf_counter()
        try:
            path = nx.shortest_path(self.graph, start, end, weight="weight")
            eta = nx.shortest_path_length(self.graph, start, end, weight="weight")
        except nx.NetworkXNoPath:
            return {"error": "No safe route available — area is cut off by flooding."}
        latency_ms = (time.perf_counter() - t0) * 1000

        coordinates = []
        roads_travelled = []

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = self.graph[u][v]
            roads_travelled.append(edge_data.get("road_name", "Unnamed Road"))

            u_lat, u_lon = self.graph.nodes[u]["lat"], self.graph.nodes[u]["lon"]
            v_lat, v_lon = self.graph.nodes[v]["lat"], self.graph.nodes[v]["lon"]

            geom = edge_data.get("geometry")
            if geom is not None:
                pts = list(geom.coords)
                first_lon, first_lat = pts[0]
                dist_to_u = abs(first_lat - u_lat) + abs(first_lon - u_lon)
                dist_to_v = abs(first_lat - v_lat) + abs(first_lon - v_lon)
                if dist_to_v < dist_to_u:
                    pts = pts[::-1]
                for lon, lat in pts:
                    coordinates.append({"lat": lat, "lon": lon})
            else:
                if not coordinates or coordinates[-1] != {"lat": u_lat, "lon": u_lon}:
                    coordinates.append({"lat": u_lat, "lon": u_lon})
                coordinates.append({"lat": v_lat, "lon": v_lon})

        return {
            "path": path,
            "coordinates": coordinates,
            "roads_travelled": roads_travelled,
            "eta_minutes": round(eta, 2) if eta != float("inf") else None,
            "calc_latency_ms": round(latency_ms, 3),
            "flooded_roads_avoided": list(self.flooded_edges.keys()),
        }

    def get_all_nodes(self):
        return [
            {"id": n, "label": d.get("label", n), "lat": d["lat"], "lon": d["lon"]}
            for n, d in self.graph.nodes(data=True)
        ]

    def get_all_edges(self):
        return [
            {
                "from": u, "to": v,
                "road_name": d.get("road_name", "Unnamed Road"),
                "weight": d["weight"],
                "flooded": (u, v) in self.flooded_edges or (v, u) in self.flooded_edges,
            }
            for u, v, d in self.graph.edges(data=True)
        ]

    def get_neighbors(self, node_id: str):
        node_id = str(node_id)
        if node_id not in self.graph:
            return []
        result = []
        for neighbor in self.graph.neighbors(node_id):
            edge = self.graph[node_id][neighbor]
            result.append({
                "id": neighbor,
                "label": self.graph.nodes[neighbor].get("label", neighbor),
                "road_name": edge.get("road_name", "Unnamed Road"),
            })
        return result