"""
scorer.py  —  Score a candidate route using per-edge ML delay predictions.

Uses a NORMALIZED 4-factor scoring formula where all components contribute
meaningfully to route selection, preventing any single factor from dominating.
"""

from __future__ import annotations

import pandas as pd
from .graph_builder import get_graph
from src.features.build_inference_features import build_feature_vector
from src.models.predict import predict_delay, get_threshold
from src.models.explain import explain_prediction
from src.simulator.hubs import get_hub
from src.utils.osrm_api import get_osrm_route

def _risk_label(prob: float) -> str:
    if prob < 0.25: return "low"
    if prob < 0.50: return "medium"
    if prob < 0.70: return "high"
    return "very_high"


# ── Normalized 4-factor scoring weights ──────────────────────────────────────
# All feature values are normalized to approximately [0, 1] range BEFORE
# weighting, so these weights reflect actual importance.
#
# W_TIME  (0.40) — Arrival speed matters most in logistics
# W_DELAY (0.25) — ML-predicted delay risk directly impacts reliability
# W_DIST  (0.20) — Fuel/distance cost matters but shouldn't dominate
# W_TRAFF (0.15) — Real-time traffic disruption factor
#
W_DIST  = 0.20
W_TIME  = 0.40
W_DELAY = 0.25
W_TRAFF = 0.15

# Normalization constants (approximate max values for Indian routes)
MAX_DISTANCE_KM = 3000.0   # Max hub-to-hub distance
MAX_TIME_HR     = 50.0     # Max expected travel time
MAX_TRAFFIC_HR  = 10.0     # Max traffic delay hours


def score_route(
    route: list[str],
    departure_time: str,
    vehicle_type: str = "van",
    cargo_type: str   = "standard",
    priority_level: int = 2,
    w1: float = W_DIST,
    w2: float = W_TIME,
    w3: float = W_DELAY,
    w4: float = W_TRAFF,
    weather_api_key: str | None = None,
    use_osrm: bool = True,
) -> dict:
    
    G = get_graph()
    segments = []
    total_distance  = 0.0
    total_time      = 0.0
    total_cost      = 0.0
    delay_probs     = []

    for i in range(len(route) - 1):
        src, dst = route[i], route[i + 1]

        if not G.has_edge(src, dst):
            raise ValueError(f"No direct edge {src} → {dst} in network.")

        edge = G[src][dst]
        edge_distance = edge["distance_km"]
        edge_time     = edge["base_time_hr"]
        geometry      = None

        if use_osrm:
            src_hub = get_hub(src)
            dst_hub = get_hub(dst)
            dist, dur, geom = get_osrm_route(
                src_hub["lat"], src_hub["lon"], 
                dst_hub["lat"], dst_hub["lon"]
            )
            if dist is not None:
                edge_distance = dist
                edge_time = dur
                geometry = geom

        total_distance += edge_distance
        total_time     += edge_time

        # Build features for this specific edge
        features = build_feature_vector(
            source              = src,
            destination         = dst,
            departure_time      = departure_time,
            vehicle_type        = vehicle_type,
            cargo_type          = cargo_type,
            priority_level      = priority_level,
            weather_api_key     = weather_api_key,
            use_osrm            = use_osrm,
        )

        prob, _delayed, pred_mins = predict_delay(features)
        
        # Extract raw values from feature vector
        traffic_time = float(features["traffic_time"].iloc[0])
        traffic_delay = float(features["traffic_delay"].iloc[0])
        dist_km = float(features["distance_km"].iloc[0])
        
        total_expected_time = traffic_time + (pred_mins / 60.0)
        
        # ── NORMALIZED scoring ──────────────────────────────────────────────
        # Normalize all components to approximately [0, 1] so weights
        # reflect true importance — no single factor can dominate.
        norm_dist    = dist_km / MAX_DISTANCE_KM             # ~0.03 to ~1.0
        norm_time    = total_expected_time / MAX_TIME_HR      # ~0.02 to ~1.0
        norm_delay   = prob                                   # already 0-1
        norm_traffic = min(traffic_delay / MAX_TRAFFIC_HR, 1) # clamp to 0-1
        
        cost_per_segment = (
            w1 * norm_dist +
            w2 * norm_time +
            w3 * norm_delay +
            w4 * norm_traffic
        )
        total_cost += cost_per_segment

        top_factors = explain_prediction(features, top_n=3)
        risk_level = _risk_label(prob)

        delay_probs.append(prob)
        segments.append({
            "from": src,
            "to": dst,
            "distance_km": round(edge_distance, 1),
            "estimated_time_hr": round(edge_time, 2),
            "traffic_time": round(traffic_time, 2),
            "traffic_delay": round(traffic_delay, 2),
            "predicted_delay_minutes": round(pred_mins, 1),
            "cost_per_segment": round(cost_per_segment, 4),
            "road_type": "highway" if use_osrm else edge["road_type"],
            "delay_probability": round(prob, 4),
            "risk_level": risk_level,
            "top_factors": top_factors,
            "geometry": geometry,
        })

    # Cumulative route-level delay probability:
    # P(at least one segment delayed) = 1 - ∏(1 - p_i)
    # This correctly shows that more segments = higher overall risk.
    no_delay_prob = 1.0
    for p in delay_probs:
        no_delay_prob *= (1.0 - p)
    route_delay_risk = 1.0 - no_delay_prob

    # Total predicted delay across all segments
    total_delay_mins = sum(s["predicted_delay_minutes"] for s in segments)

    return {
        "route": route,
        "n_hops": len(route) - 1,
        "total_distance_km": round(total_distance, 1),
        "estimated_time_hr": round(total_time, 2),
        "mean_delay_risk": round(route_delay_risk, 4),
        "total_predicted_delay_minutes": round(total_delay_mins, 1),
        "route_score": round(total_cost, 4),
        "segments": segments,
    }
