"""
vrp.py  —  Multi-Stop Vehicle Routing Problem (VRP) Solver.

Scales up from A->B routing to optimized multi-stop delivery routes.
Given an Origin and N Destinations, it finds the best mathematical order
to visit all destinations, minimizing total time, distance, and delay risk
using our 3-Factor ML Scoring Engine.
"""

from __future__ import annotations
import itertools

from .optimizer import find_best_route


def optimize_fleet_route(
    source: str,
    destinations: list[str],
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str = "standard",
    priority_level: int = 2,
    weather_api_key: str | None = None,
    max_candidates_per_leg: int = 5,
) -> dict:
    """
    Solve the Traveling Salesperson Problem (TSP) for multi-stop delivery.
    
    Returns the optimal sequence of stops and the combined route details.
    """
    if not destinations:
        raise ValueError("Must provide at least one destination.")
        
    if len(destinations) > 6:
        # Prevent combinatorial explosion; cap at 6 stops for real-time API
        raise ValueError("Maximum 6 destinations allowed for real-time fleet optimization.")

    # Generate all possible delivery orders
    permutations = list(itertools.permutations(destinations))
    
    best_overall_score = float("inf")
    best_vrp_plan = None
    
    # Cache legs to avoid redundant ML/OSRM API calls A->B and B->A
    leg_cache = {}
    
    scored_plans = []

    for order in permutations:
        # Full path sequence: Source -> Stop 1 -> Stop 2 ...
        sequence = [source] + list(order)
        
        sequence_score = 0.0
        total_dist = 0.0
        total_time = 0.0
        legs = []
        is_valid = True
        
        # Calculate each leg of the journey
        for i in range(len(sequence) - 1):
            leg_src = sequence[i]
            leg_dst = sequence[i+1]
            cache_key = f"{leg_src}->{leg_dst}"
            
            if cache_key not in leg_cache:
                try:
                    res = find_best_route(
                        source=leg_src,
                        destination=leg_dst,
                        departure_time=departure_time, # Future: increment departure_time based on previous leg ETA
                        vehicle_type=vehicle_type,
                        cargo_type=cargo_type,
                        priority_level=priority_level,
                        max_candidates=max_candidates_per_leg,
                        use_osrm=True
                    )
                    leg_cache[cache_key] = res
                except Exception as e:
                    import traceback
                    print(f"[VRP ERROR] Failed to score leg {cache_key}: {e}")
                    traceback.print_exc()
                    leg_cache[cache_key] = None
                    
            leg_res = leg_cache[cache_key]
            
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
                "route": leg_best["route"], # The internal hubs used
                "segments": leg_best["segments"],
                "leg_score": leg_best["route_score"],
                "alternatives": leg_alts
            })
            
        if is_valid:
            plan = {
                "visit_order": [source] + list(order),
                "total_score": round(sequence_score, 4),
                "total_distance_km": round(total_dist, 1),
                "total_estimated_time_hr": round(total_time, 2),
                "legs": legs
            }
            scored_plans.append(plan)
            
            if sequence_score < best_overall_score:
                best_overall_score = sequence_score
                best_vrp_plan = plan

    if not best_vrp_plan:
        raise ValueError("Could not find a valid multi-stop route connecting all destinations.")

    # Sort plans by score
    scored_plans.sort(key=lambda x: x["total_score"])

    return {
        "source": source,
        "destinations": destinations,
        "best_plan": best_vrp_plan,
        "alternatives": scored_plans[1:4] # Return top 3 alternatives
    }
