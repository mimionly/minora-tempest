"""
One-time offline export: OSM road network -> data/region_graph.json
Never runs during the live demo. Run manually whenever you need to
(re)generate the graph for your region.
"""

import argparse
import json
import sys
import time
import networkx as nx
import osmnx as ox
import requests


def fetch_elevation_batch(coords, batch_size=100):
    """
    Queries the free Open-Elevation API in batches.
    On failure for a batch, defaults those points to 0.0m and logs a warning
    instead of failing the whole export.
    """
    elevations = []
    for i in range(0, len(coords), batch_size):
        batch = coords[i:i + batch_size]
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in batch]
        try:
            resp = requests.post(
                "https://api.open-elevation.com/api/v1/lookup",
                json={"locations": locations},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()["results"]
            elevations.extend([r["elevation"] for r in results])
        except Exception as e:
            print(f"WARNING: elevation batch {i}-{i+batch_size} failed ({e}); defaulting to 0.0m")
            elevations.extend([0.0] * len(batch))
        time.sleep(0.2)  # be polite to the free API
    return elevations


def prune_to_largest_component(g):
    """
    Guarantees no silent 'unreachable node' failures at demo time by keeping
    only the largest strongly-connected component.
    """
    if g.is_directed():
        components = list(nx.strongly_connected_components(g))
    else:
        components = list(nx.connected_components(g))
    largest = max(components, key=len)
    removed = g.number_of_nodes() - len(largest)
    if removed > 0:
        print(f"Pruning {removed} disconnected nodes (keeping largest component: {len(largest)} nodes)")
    return g.subgraph(largest).copy()


def load_safe_zones(path):
    if not path:
        return []
    with open(path) as f:
        return json.load(f)


def snap_safe_zones(g, safe_zones):
    """Finds the nearest graph node to each hand-curated safe zone coordinate."""
    tagged = []
    for zone in safe_zones:
        try:
            node_id = ox.distance.nearest_nodes(g, zone["lon"], zone["lat"])
            tagged.append({**zone, "node_id": str(node_id)})
        except Exception as e:
            print(f"WARNING: could not snap safe zone '{zone.get('name')}' ({e})")
    return tagged


def build(place, dist_meters, out_path, safe_zones_path, dry_run):
    print(f"Fetching road network for: {place} (radius {dist_meters}m)...")
    g = ox.graph_from_address(place, dist=dist_meters, network_type="drive")
    print(f"Raw graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    g = prune_to_largest_component(g)
    print(f"After pruning: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    if dry_run:
        print("Dry run complete — no file written. Adjust --dist or --place if these numbers look wrong.")
        return

    # Relabel node IDs to strings once, permanently — avoids int/string
    # mismatch bugs anywhere downstream (backend, API, frontend).
    g = nx.relabel_nodes(g, {n: str(n) for n in g.nodes})

    print("Fetching elevation for every node (this can take a few minutes)...")
    node_ids = list(g.nodes)
    coords = [(g.nodes[n]["y"], g.nodes[n]["x"]) for n in node_ids]
    elevations = fetch_elevation_batch(coords)
    for node_id, elev in zip(node_ids, elevations):
        g.nodes[node_id]["elevation_m"] = elev

    safe_zones = load_safe_zones(safe_zones_path)
    tagged_zones = snap_safe_zones(g, safe_zones)
    safe_zone_by_node = {z["node_id"]: z for z in tagged_zones}

    # ---- Build the STATIC export payload ----
    # No risk_score / depth_cm / blocked here — those are runtime-owned by
    # the backend and must never be baked into the static export.
    nodes_out = []
    for n, data in g.nodes(data=True):
        zone = safe_zone_by_node.get(n)
        nodes_out.append({
            "id": n,
            "lat": data["y"],
            "lon": data["x"],
            "elevation_m": round(data.get("elevation_m", 0.0), 2),
            "type": zone["type"] if zone else "intersection",
            "name": zone["name"] if zone else "",
        })

    edges_out = []
    seen = set()
    for u, v, data in g.edges(data=True):
        key = tuple(sorted([u, v]))
        if key in seen:
            continue
        seen.add(key)

        length_m = data.get("length", 100)
        base_speed_kph = 30  # simple fixed assumption; adjust per highway type if you want more realism
        travel_time_s = (length_m / 1000 / base_speed_kph) * 3600

        raw_name = data.get("name", "Unnamed Road")
        road_name = raw_name[0] if isinstance(raw_name, list) else raw_name

        edges_out.append({
            "from": u,
            "to": v,
            "length_m": round(length_m, 1),
            "base_speed_kph": base_speed_kph,
            "travel_time_s": round(travel_time_s, 2),
            "highway": str(data.get("highway", "unknown")),
            "name": road_name or "Unnamed Road",
        })

    payload = {
        "place": place,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "nodes": nodes_out,
        "edges": edges_out,
        "safe_zones": tagged_zones,
    }

    with open(out_path, "w") as f:
        json.dump(payload, f)

    print(f"Wrote {out_path}: {len(nodes_out)} nodes, {len(edges_out)} edges, {len(tagged_zones)} safe zones")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--place", required=True, help='e.g. "Mangaluru, Karnataka, India"')
    parser.add_argument("--dist", type=int, default=8000, help="Radius in meters (default 8000)")
    parser.add_argument("--out", default="../data/region_graph.json")
    parser.add_argument("--tags", default=None, help="Path to safe_zones.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        build(args.place, args.dist, args.out, args.tags, args.dry_run)
    except Exception as e:
        print(f"FATAL: export failed — {e}", file=sys.stderr)
        sys.exit(1)