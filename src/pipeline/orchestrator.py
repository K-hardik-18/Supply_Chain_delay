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
        # Normalise VRP output: vrp.py returns "best_plan" (not "fleet_plan")
        # Attach total_cost alias and per-leg leg_cost so downstream consumers
        # and the FleetOptimizationResponse schema can read them consistently.
        if "best_plan" in res:
            plan = res["best_plan"]
            plan["total_cost"] = plan.get("total_score", 0.0)
            for leg in plan.get("legs", []):
                leg["leg_cost"] = leg.get("leg_score", 0.0)

        return res
