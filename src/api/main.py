"""
main.py  —  FastAPI application for logistics delay prediction and route optimization.

Start:
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

Endpoints:
    GET  /              → Frontend dashboard
    GET  /health        → health check with model and graph status
    GET  /hubs          → list all available hubs with coordinates
    POST /predict-delay → predict shipment delay probability + SHAP explanation
    POST /optimize-route → score and rank candidate routes
    GET  /history       → recent prediction history
    GET  /analytics     → aggregate analytics and trends
"""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    DelayRequest, DelayResponse,
    RouteRequest, RouteResponse,
    FleetOptimizationRequest, FleetOptimizationResponse,
    HealthResponse, RiskLevel,
)
from src.features.build_inference_features import (
    build_feature_vector, get_feature_metadata,
)
from src.models.predict import predict_delay, _load_bundle, get_model_name
from src.models.explain import explain_prediction
from src.routing.graph_builder import get_graph, graph_summary
from src.routing.optimizer import find_best_route
from src.pipeline.orchestrator import run_orchestrator
from src.simulator.hubs import HUBS, CITY_NAMES
from src.db.history import save_prediction, save_route, get_predictions, get_routes, get_analytics

from dotenv import find_dotenv
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = find_dotenv(usecwd=True) or os.path.join(_project_root, ".env")
load_dotenv(_env_path)
WEATHER_API_KEY      = os.getenv("OPENWEATHER_API_KEY")
MODEL_PATH           = os.getenv("MODEL_PATH", "models/delay_classifier.pkl")
TOMTOM_API_KEY       = os.getenv("TOMTOM_API_KEY")
# OSRM is used as the free routing API by default.
USE_OSRM             = True


# ── Startup / shutdown lifecycle ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up model and graph on startup (avoids cold-start latency)
    try:
        _load_bundle(MODEL_PATH)
        G = get_graph()
        info = graph_summary(G)
        model_name = get_model_name(MODEL_PATH)
        print(f"Model loaded   : {MODEL_PATH} ({model_name})")
        print(f"Graph ready    : {info['nodes']} hubs, {info['edges']} edges")
        if USE_OSRM:
            print(f"Routing API    : OSRM Public API (enabled)")
        else:
            print(f"Routing API    : disabled (using haversine fallback)")
        print(f"Weather API    : {'✅ OpenWeatherMap (live)' if WEATHER_API_KEY else '⚠️ No key — simulated fallback'}")
        print(f"History DB     : data/history.db (active)")
    except Exception as e:
        print(f"[WARNING] Startup init failed: {e}")
    yield


app = FastAPI(
    title       = "Smart Logistics Intelligence API",
    description = (
        "Multi-model delay prediction (LR / RF / XGBoost) with SHAP explainability, "
        "3-factor ML-powered route optimization (time + delay risk + distance), "
        "and free OSRM public API routing integration."
    ),
    version     = "3.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# Serve frontend static files (CSS, JS)
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")
    
    # Enable fallback for direct file opening by mounting individual files directly
    @app.get("/style.css", include_in_schema=False)
    def serve_css(): return FileResponse(os.path.join(_frontend_dir, "style.css"))
    
    @app.get("/app.js", include_in_schema=False)
    def serve_js(): return FileResponse(os.path.join(_frontend_dir, "app.js"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _risk_label(prob: float) -> RiskLevel:
    if prob < 0.25: return "low"
    if prob < 0.50: return "medium"
    if prob < 0.70: return "high"
    return "very_high"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Serve the frontend dashboard."""
    index_path = os.path.join(_frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Smart Logistics Intelligence API", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """API health check — returns model info and graph status."""
    try:
        _load_bundle(MODEL_PATH)
        model_loaded = True
        model_name   = get_model_name(MODEL_PATH)
    except Exception:
        model_loaded = False
        model_name   = "unknown"

    G    = get_graph()
    info = graph_summary(G)

    return HealthResponse(
        status       = "ok",
        model_loaded = model_loaded,
        model_name   = model_name,
        graph_nodes  = info["nodes"],
        graph_edges  = info["edges"],
        hubs         = info["hub_list"],
    )


@app.get("/hubs", tags=["Data"])
def list_hubs():
    """Return all available hubs with lat/lon coordinates and type info."""
    # We still keep this for the "Quick Defaults" dropdown if needed
    hubs_with_coords = []
    for h in sorted(HUBS, key=lambda x: x["city"]):
        hubs_with_coords.append({
            "city": h["city"],
            "lat": h["lat"],
            "lon": h["lon"],
            "type": h["type"],
            "capacity": h["capacity"],
        })
    return {
        "hubs": sorted(CITY_NAMES),
        "hub_details": hubs_with_coords,
    }


@app.post("/predict-delay", response_model=DelayResponse, tags=["Prediction"])
def predict_delay_endpoint(req: DelayRequest):
    """
    Predict whether a shipment will be delayed and explain the top contributing factors.
    Results are automatically saved to history.
    """
    try:
        features = build_feature_vector(
            source              = req.source,
            destination         = req.destination,
            departure_time      = req.departure_time,
            vehicle_type        = req.vehicle_type,
            cargo_type          = req.cargo_type,
            priority_level      = req.priority_level,
            weather_api_key     = WEATHER_API_KEY,
            traffic_api_key     = TOMTOM_API_KEY,
            use_osrm            = USE_OSRM,
        )

        prob, delayed = predict_delay(features, model_path=MODEL_PATH)

        top_factors = explain_prediction(features, top_n=3, model_path=MODEL_PATH)

        context = get_feature_metadata(
            source         = req.source,
            destination    = req.destination,
            departure_time = req.departure_time,
            vehicle_type   = req.vehicle_type,
            cargo_type     = req.cargo_type,
            priority_level = req.priority_level,
            weather_api_key= WEATHER_API_KEY,
        )

        response_data = DelayResponse(
            source            = req.source,
            destination       = req.destination,
            departure_time    = req.departure_time,
            vehicle_type      = req.vehicle_type,
            cargo_type        = req.cargo_type,
            delay_probability = round(prob, 4),
            delayed           = delayed,
            risk_level        = _risk_label(prob),
            context           = context,
            top_factors       = top_factors,
        )

        # Auto-save to history
        try:
            save_prediction(
                request=req.model_dump(),
                response=response_data.model_dump(),
                model_name=get_model_name(MODEL_PATH),
            )
        except Exception as e:
            print(f"[WARN] History save failed: {e}")

        return response_data

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@app.post("/optimize-route", response_model=RouteResponse, tags=["Routing"])
def optimize_route_endpoint(req: RouteRequest):
    """
    Generate and score candidate routes between two hubs.
    Results are automatically saved to history.
    """
    try:
        result = find_best_route(
            source              = req.source,
            destination         = req.destination,
            departure_time      = req.departure_time,
            vehicle_type        = req.vehicle_type,
            cargo_type          = req.cargo_type,
            priority_level      = req.priority_level,
            weather_api_key     = WEATHER_API_KEY,
            use_osrm            = USE_OSRM,
        )

        # Auto-save to history
        try:
            save_route(request=req.model_dump(), response=result)
        except Exception as e:
            print(f"[WARN] Route history save failed: {e}")

        return RouteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route optimization failed: {e}")

@app.post("/predict-route", response_model=FleetOptimizationResponse, tags=["Routing"])
def predict_route_endpoint(req: FleetOptimizationRequest):
    """
    Unified Orchestrator Endpoint for Single or Multi-Destination Fleet Routing.
    """
    try:
        result = run_orchestrator(
            source              = req.source,
            destinations        = req.destinations,
            departure_time      = req.departure_time,
            vehicle_type        = req.vehicle_type,
            cargo_type          = req.cargo_type,
            priority_level      = req.priority_level,
            weather_api_key     = WEATHER_API_KEY,
        )

        return FleetOptimizationResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Predict route fleet optimization failed: {e}")


# ── History & Analytics ───────────────────────────────────────────────────────

@app.get("/history", tags=["History"])
def get_history(
    limit: int = Query(default=50, le=200, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """Return recent prediction and route optimization history."""
    predictions = get_predictions(limit=limit, offset=offset)
    routes = get_routes(limit=limit, offset=offset)
    return {
        "predictions": predictions,
        "routes": routes,
    }


@app.get("/analytics", tags=["History"])
def analytics_endpoint():
    """
    Return aggregate analytics:
    - Total predictions & routes
    - Average delay probability
    - Risk distribution (low/medium/high/very_high counts)
    - Top 5 riskiest routes
    - Hourly delay trends
    - Recent predictions
    """
    return get_analytics()
