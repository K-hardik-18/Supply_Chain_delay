"""
graph_builder.py  —  Build the base NetworkX DiGraph from network.csv.

The graph is loaded ONCE on API startup and reused across requests.
Delay risk is NOT baked into the graph — it is computed per-request in scorer.py.
"""

import pandas as pd
import networkx as nx
from pathlib import Path
from functools import lru_cache

NETWORK_PATH = "data/network.csv"


@lru_cache(maxsize=1)
def get_graph(network_path: str = NETWORK_PATH) -> nx.DiGraph:
    """
    Load network.csv and build a directed graph.

    Edge attributes stored:
        distance_km      float
        base_time_hr     float
        road_type        str   ("city" | "regional" | "highway")
        road_type_code   int
        src_lat, src_lon float
        dst_lat, dst_lon float
    """
    df = pd.read_csv(network_path)
    G  = nx.DiGraph()

    for _, row in df.iterrows():
        G.add_edge(
            row["source"],
            row["destination"],
            distance_km    = float(row["distance_km"]),
            base_time_hr   = float(row["base_time_hr"]),
            road_type      = row["road_type"],
            road_type_code = int(row["road_type_code"]),
            src_lat        = float(row["src_lat"]),
            src_lon        = float(row["src_lon"]),
            dst_lat        = float(row["dst_lat"]),
            dst_lon        = float(row["dst_lon"]),
        )

    return G


def graph_summary(G: nx.DiGraph) -> dict:
    return {
        "nodes":     G.number_of_nodes(),
        "edges":     G.number_of_edges(),
        "hub_list":  sorted(G.nodes()),
    }
