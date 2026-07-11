import os
import osmnx as ox

from graph.graph_store import graph
import graph.graph_store as store

from config import CITY
from config import CACHE_GRAPH

from config import NETWORK_TYPE


def load_graph():

    if os.path.exists(CACHE_GRAPH):

        print("Loading cached graph...")

        G = ox.load_graphml(CACHE_GRAPH)

    else:

        print("Downloading graph from OpenStreetMap...")

        G = ox.graph_from_place(
            CITY,
            network_type=NETWORK_TYPE
        )

        ox.save_graphml(G, CACHE_GRAPH)

    store.graph = G

    print()

    print("Graph Loaded")

    print("----------------------")

    print("Nodes :", len(G.nodes))

    print("Edges :", len(G.edges))

    print()