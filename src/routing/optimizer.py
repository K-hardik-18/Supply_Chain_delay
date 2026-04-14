"""
optimizer.py  —  The central routing engine.

Finds candidate routes using NetworkX (shortest path by hops, shortest by distance,
alternative paths), then scores each path using the ML delay prediction model.
Returns the absolute best route (lowest score) and up to N alternatives.
"""

from __future__ import annotations
import networkx as nx

from .graph_builder import get_graph
from .scorer import score_route

def find_best_route(
    source: str,
    destination: str,
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str   = "standard",
    priority_level: int = 2,
    max_candidates: int = 3,
    weather_api_key: str | None = None,
    use_osrm: bool = True,
) -> dict:
    
    G = get_graph()
    if source not in G or destination not in G:
        raise ValueError(f"Unknown source or destination. Valid hubs: {list(G.nodes())}")

    # Generate up to N logical paths through the static fully-connected graph
    try:
        paths_generator = nx.shortest_simple_paths(G, source, destination, weight="distance_km")
        candidate_paths = []
        for p in paths_generator:
            candidate_paths.append(p)
            if len(candidate_paths) >= max_candidates:
                break
    except nx.NetworkXNoPath:
        raise ValueError(f"No path exists between {source} and {destination}.")

    scored_routes = []
    for path in candidate_paths:
        try:
            res = score_route(
                route=path,
                departure_time=departure_time,
                vehicle_type=vehicle_type,
                cargo_type=cargo_type,
                priority_level=priority_level,
                weather_api_key=weather_api_key,
                use_osrm=use_osrm,
            )
            scored_routes.append(res)
        except Exception as e:
            print(f"Failed to score candidate path {path}: {e}")

    if not scored_routes:
        raise ValueError("Could not score any valid routes.")

    # Sort by the 4-factor composite score: distance + time + delay risk + traffic (lower is better)
    scored_routes.sort(key=lambda x: x["route_score"])

    best = scored_routes[0]
    alternatives = scored_routes[1:]

    return {
        "best_route": best,
        "alternatives": alternatives,
        "summary": {
            "n_candidates": len(scored_routes),
            "best_score": best["route_score"],
            "best_time_hr": best["estimated_time_hr"],
            "best_delay_risk": best["mean_delay_risk"],
        }
    }
