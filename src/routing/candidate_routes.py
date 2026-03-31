"""
candidate_routes.py  —  Generate K candidate routes between two hubs.

Strategy:
  1. Shortest by distance (Dijkstra)
  2. Shortest by base travel time (Dijkstra)
  3. Up to (max_candidates - 2) simple-path alternatives, filtered by max hops

All routes are returned as lists of hub city strings.
"""

import networkx as nx
from .graph_builder import get_graph

MAX_CANDIDATES = 5
MAX_HOPS       = 3          # max intermediate hubs (so total path len ≤ MAX_HOPS + 2)
MAX_EDGE_KM    = 450        # only edges ≤ this distance are considered


def generate_candidate_routes(
    source: str,
    destination: str,
    max_candidates: int = MAX_CANDIDATES,
    max_hops: int = MAX_HOPS,
) -> list[list[str]]:
    """
    Return a de-duplicated list of candidate routes (each a list of hub names).
    Raises ValueError if source/destination not in graph or not connected.
    """
    G = get_graph()

    if source not in G:
        raise ValueError(f"Source hub '{source}' not in network.")
    if destination not in G:
        raise ValueError(f"Destination hub '{destination}' not in network.")

    candidates: list[list[str]] = []
    seen: set[tuple] = set()

    def _add(path: list[str]):
        key = tuple(path)
        if key not in seen and len(path) <= max_hops + 2:
            seen.add(key)
            candidates.append(path)

    # ── Route 1: shortest by distance ────────────────────────────────────────
    try:
        r1 = nx.shortest_path(G, source, destination, weight="distance_km")
        _add(r1)
    except nx.NetworkXNoPath:
        raise ValueError(f"No path exists between {source} and {destination}.")

    # ── Route 2: shortest by travel time ─────────────────────────────────────
    try:
        r2 = nx.shortest_path(G, source, destination, weight="base_time_hr")
        _add(r2)
    except nx.NetworkXNoPath:
        pass

    # ── Routes 3+: simple-path alternatives ──────────────────────────────────
    try:
        for path in nx.shortest_simple_paths(G, source, destination, weight="distance_km"):
            if len(candidates) >= max_candidates:
                break
            _add(path)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass

    return candidates[:max_candidates]
