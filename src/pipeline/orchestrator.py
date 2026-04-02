"""
orchestrator.py — The top-level Master Controller handling routing logic.

Decides between direct single-destination routing and multi-stop VRP optimization, 
piping input cleanly into the optimization layers which inherently hit APIs (OSRM, TomTom)
and parse the predictive scores.
"""

from src.routing.optimizer import find_best_route
from src.routing.vrp import optimize_fleet_route

def run_orchestrator(
    source: str,
    destinations: list[str],
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str = "standard",
    priority_level: int = 2,
    weather_api_key: str | None = None,
) -> dict:
    """
    Main controller endpoint mapping to the exact 9-step requirement architecture.
    """
    if not destinations:
        raise ValueError("Must provide at least one destination.")

    # Single-destination dispatch
    if len(destinations) == 1:
        res = find_best_route(
            source=source,
            destination=destinations[0],
            departure_time=departure_time,
            vehicle_type=vehicle_type,
            cargo_type=cargo_type,
            priority_level=priority_level,
            max_candidates=3,          # Keep candidates constrained for singles
            weather_api_key=weather_api_key,
            use_osrm=True
        )
        plan = {
            "source": source,
            "destinations": destinations,
            "best_plan": {
                "visit_order": [source, destinations[0]],
                "total_score": res["best_route"]["route_score"],
                "total_distance_km": res["best_route"]["total_distance_km"],
                "total_estimated_time_hr": res["best_route"]["estimated_time_hr"],
                "legs": [
                    {
                        "from_stop": source,
                        "to_stop": destinations[0],
                        "route": res["best_route"]["route"],
                        "segments": res["best_route"]["segments"],
                        "leg_score": res["best_route"]["route_score"],
                        "alternatives": res.get("alternatives", [])
                    }
                ]
            },
            "alternatives": []
        }
        return plan

    # Multi-destination VRP dispatch
    else:
        res = optimize_fleet_route(
            source=source,
            destinations=destinations,
            departure_time=departure_time,
            vehicle_type=vehicle_type,
            cargo_type=cargo_type,
            priority_level=priority_level,
            weather_api_key=weather_api_key,
            max_candidates_per_leg=3,
        )
        # Mutate vrp output to attach total_cost specifically for step 8 schema
        if "fleet_plan" in res:
            res["fleet_plan"]["total_cost"] = res["fleet_plan"]["total_route_score"]
            for leg in res["fleet_plan"]["legs"]:
                leg["leg_cost"] = leg["leg_score"]
                
        return res
