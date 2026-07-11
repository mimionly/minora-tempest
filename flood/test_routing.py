import os
import networkx as nx
import pandas as pd
import numpy as np

import requests
def geocode(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}, Mangaluru"
    headers = {"User-Agent": "FloodRouteApp/1.0"}
    res = requests.get(url, headers=headers).json()
    return [float(res[0]['lat']), float(res[0]['lon'])]

c_mangaladevi = geocode("mangaladevi")
c_bolar = geocode("bolar")

print("Mangaladevi:", c_mangaladevi)
print("Bolar:", c_bolar)

from app import CoastalFloodRouter
router = CoastalFloodRouter()
router.load_network_if_new("Mangaluru")


score, tier, submerged, warnings, green_nodes, fallback_nodes = router.adapt_network_weights(
    c_mangaladevi[0], c_mangaladevi[1], ""
)

print(f"Risk Score: {score}")

def test_fallback_route(start, end, name):
    print(f"\nTesting Fallback Route: {name}")
    try:
        orig = router._nearest_safe_node(start[0], start[1], fallback_nodes)
        dest = router._nearest_safe_node(end[0], end[1], fallback_nodes)
        
        def not_blocked(u, v, k):
            return not router.graph.edges[u, v, k].get('is_blocked', False)
        fallback_graph = nx.subgraph_view(router.graph, filter_edge=not_blocked)
        
        path = nx.shortest_path(fallback_graph, source=orig, target=dest, weight='current_weight')
        print(f"Fallback path length: {len(path)}")
        for u, v in zip(path[:-1], path[1:]):
            prox_u = router._node_prox_factor.get(u, 1.0)
            prox_v = router._node_prox_factor.get(v, 1.0)
            risk_u = score * prox_u
            risk_v = score * prox_v
            
            # Check if reverse edge exists and is blocked
            reverse_exists = router.graph.has_edge(v, u)
            if reverse_exists:
                rev_blocked = router.graph.edges[v, u, 0].get('is_blocked', False)
                print(f"Edge {u}->{v}: risk_u={risk_u:.1f}, risk_v={risk_v:.1f} | Reverse {v}->{u} exists, is_blocked={rev_blocked}")
            else:
                print(f"Edge {u}->{v}: risk_u={risk_u:.1f}, risk_v={risk_v:.1f} | Reverse {v}->{u} DOES NOT EXIST (One-way)")
    except Exception as e:
        print("Error tracing path:", e)

test_fallback_route(c_bolar, c_mangaladevi, "Bolar -> Mangaladevi")
test_fallback_route(c_mangaladevi, c_bolar, "Mangaladevi -> Bolar")


