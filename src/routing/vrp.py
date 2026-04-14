"""
vrp.py  —  Multi-Stop Vehicle Routing Problem (VRP) Solver.

Uses a fast nearest-neighbor heuristic for ordering, then evaluates the top
permutations to find the optimal route. Avoids brute-force O(N!) for > 3 stops.
"""

from __future__ import annotations
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

from .optimizer import find_best_route
from .graph_builder import get_graph


def _score_leg(
    leg_src: str,
    leg_dst: str,
    departure_time: str,
    vehicle_type: str,
    cargo_type: str,
    priority_level: int,
    max_candidates: int,
    weather_api_key: str | None,
) -> dict | None:
    """Score a single leg; returns None on failure."""
    try:
        return find_best_route(
            source=leg_src,
            destination=leg_dst,
            departure_time=departure_time,
            vehicle_type=vehicle_type,
            cargo_type=cargo_type,
            priority_level=priority_level,
            max_candidates=max_candidates,
            weather_api_key=weather_api_key,
            use_osrm=True,
        )
    except Exception as e:
        print(f"[VRP] Leg {leg_src}→{leg_dst} failed: {e}")
        return None


def _nearest_neighbor_order(source: str, destinations: list[str]) -> list[str]:
    """
    Greedy nearest-neighbor heuristic using graph edge distances.
    Returns a permutation that visits the closest unvisited hub next.
    """
    G = get_graph()
    remaining = list(destinations)
    order = []
    current = source

    while remaining:
        best_dst = min(remaining, key=lambda d: G[current][d]["distance_km"] if G.has_edge(current, d) else float("inf"))
        order.append(best_dst)
        current = best_dst
        remaining.remove(best_dst)

    return order


def optimize_fleet_route(
    source: str,
    destinations: list[str],
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str = "standard",
    priority_level: int = 2,
    weather_api_key: str | None = None,
    max_candidates_per_leg: int = 3,
) -> dict:
    """
    Solve the multi-stop VRP.
    
    For ≤3 destinations (≤6 permutations): evaluates ALL permutations.
    For >3 destinations: uses nearest-neighbor + reverse as smart candidates.
    """
    if not destinations:
        raise ValueError("Must provide at least one destination.")
    if len(destinations) > 6:
        raise ValueError("Maximum 6 destinations allowed for real-time fleet optimization.")

    # --- Decide which orderings to evaluate ---
    orderings = []

    if len(destinations) <= 3:
        # ≤6 permutations — brute force is fast enough
        orderings = list(itertools.permutations(destinations))
    else:
        # Use nearest-neighbor heuristic + reverse (top 2 candidates)
        nn_order = _nearest_neighbor_order(source, destinations)
        orderings = [tuple(nn_order), tuple(reversed(nn_order))]

    # --- Add hub-and-spoke orderings (return to source between stops) ---
    # This relaxes strict TSP: sometimes backtracking through origin is faster
    # than direct travel (e.g., origin = Delhi, destinations = Jaipur + Chennai;
    # going Delhi→Jaipur→Delhi→Chennai may be faster than Delhi→Jaipur→Chennai).
    nn_order = _nearest_neighbor_order(source, destinations)
    spoke_sequence = []
    for d in nn_order:
        spoke_sequence.append(d)
        spoke_sequence.append(source)  # return to source after each stop
    spoke_sequence.pop()  # remove trailing source
    orderings.append(tuple(spoke_sequence))

    # Deduplicate orderings
    orderings = list(set(orderings))

    # --- Pre-compute all unique legs in parallel ---
    unique_legs = set()
    for order in orderings:
        seq = [source] + list(order)
        for i in range(len(seq) - 1):
            unique_legs.add((seq[i], seq[i + 1]))

    leg_cache: dict[str, dict | None] = {}

    # Parallel leg scoring using thread pool
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for (ls, ld) in unique_legs:
            key = f"{ls}->{ld}"
            if key not in futures:
                futures[key] = executor.submit(
                    _score_leg, ls, ld,
                    departure_time, vehicle_type, cargo_type,
                    priority_level, max_candidates_per_leg, weather_api_key,
                )

        for key, future in futures.items():
            try:
                leg_cache[key] = future.result(timeout=60)
            except Exception as e:
                print(f"[VRP] Parallel leg {key} failed: {e}")
                leg_cache[key] = None

    # --- Evaluate each ordering using cached legs ---
    best_overall_score = float("inf")
    best_vrp_plan = None
    scored_plans = []

    for order in orderings:
        sequence = [source] + list(order)
        sequence_score = 0.0
        total_dist = 0.0
        total_time = 0.0
        legs = []
        is_valid = True

        for i in range(len(sequence) - 1):
            leg_src = sequence[i]
            leg_dst = sequence[i + 1]
            cache_key = f"{leg_src}->{leg_dst}"
            leg_res = leg_cache.get(cache_key)

            if not leg_res:
                is_valid = False
                break

            leg_best = leg_res["best_route"]
            leg_alts = leg_res.get("alternatives", [])

            sequence_score += leg_best["route_score"]
            total_dist += leg_best["total_distance_km"]
            total_time += leg_best["estimated_time_hr"]

            legs.append({
                "from_stop": leg_src,
                "to_stop": leg_dst,
                "route": leg_best["route"],
                "segments": leg_best["segments"],
                "leg_score": leg_best["route_score"],
                "alternatives": leg_alts,
            })

        if is_valid:
            plan = {
                "visit_order": [source] + list(order),
                "total_score": round(sequence_score, 4),
                "total_distance_km": round(total_dist, 1),
                "total_estimated_time_hr": round(total_time, 2),
                "legs": legs,
            }
            scored_plans.append(plan)

            if sequence_score < best_overall_score:
                best_overall_score = sequence_score
                best_vrp_plan = plan

    if not best_vrp_plan:
        raise ValueError("Could not find a valid multi-stop route connecting all destinations.")

    scored_plans.sort(key=lambda x: x["total_score"])

    return {
        "source": source,
        "destinations": destinations,
        "best_plan": best_vrp_plan,
        "alternatives": scored_plans[1:4],
    }
