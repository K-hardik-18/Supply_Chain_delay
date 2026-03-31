"""
schemas.py  —  Pydantic request and response models for the API.

Keeps main.py thin. All field validation lives here.
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ── Shared enums ─────────────────────────────────────────────────────────────

VehicleType  = Literal["bike", "van", "truck"]
CargoType    = Literal["standard", "perishable", "fragile"]
PriorityLevel = Literal[1, 2, 3]
RiskLevel    = Literal["low", "medium", "high", "very_high"]
Direction    = Literal["increases_risk", "reduces_risk"]


# ── Request models ────────────────────────────────────────────────────────────

class DelayRequest(BaseModel):
    source:         str          = Field(..., example="Jaipur")
    destination:    str          = Field(..., example="Lucknow")
    departure_time: str          = Field(..., example="2024-07-15T09:30:00",
                                         description="ISO 8601 datetime")
    vehicle_type:   VehicleType  = Field(default="van")
    cargo_type:     CargoType    = Field(default="standard")
    priority_level: PriorityLevel = Field(default=2)

    @field_validator("departure_time")
    @classmethod
    def validate_iso(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("departure_time must be ISO 8601 format, e.g. '2024-07-15T09:30:00'")
        return v


class RouteRequest(DelayRequest):
    """Same fields as DelayRequest — inherits all validation."""
    pass


class FleetOptimizationRequest(BaseModel):
    source:         str          = Field(..., example="Jaipur")
    destinations:   list[str]    = Field(..., example=["Agra", "Delhi", "Lucknow"])
    departure_time: str          = Field(..., example="2024-07-15T09:30:00", description="ISO 8601 datetime")
    vehicle_type:   VehicleType  = Field(default="van")
    cargo_type:     CargoType    = Field(default="standard")
    priority_level: PriorityLevel = Field(default=2)

    @field_validator("departure_time")
    @classmethod
    def validate_iso(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("departure_time must be ISO 8601 format")
        return v
        
    @field_validator("destinations")
    @classmethod
    def validate_destinations(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Must provide at least one destination.")
        if len(set(v)) != len(v):
            pass # We could deduplicate or error, but let's just allow it or let VRP handle it
        if len(v) > 6:
            raise ValueError("Maximum 6 destinations allowed for real-time fleet optimization.")
        return v


# ── Response models ───────────────────────────────────────────────────────────

class ShapFactor(BaseModel):
    feature:    str
    label:      str
    value:      float
    shap_value: float
    direction:  Direction
    magnitude:  float


class DelayResponse(BaseModel):
    source:            str
    destination:       str
    departure_time:    str
    vehicle_type:      VehicleType
    cargo_type:        CargoType
    delay_probability: float = Field(..., ge=0.0, le=1.0)
    delayed:           bool
    risk_level:        RiskLevel
    context: dict = Field(
        description="Human-readable snapshot: traffic, weather, distance, etc."
    )
    top_factors: list[ShapFactor] = Field(
        description="Top 3 SHAP contributors to this prediction"
    )


class RouteSegment(BaseModel):
    from_hub:          str = Field(alias="from")
    to_hub:            str = Field(alias="to")
    distance_km:       float
    estimated_time_hr: float
    traffic_time:      float = Field(default=0.0)
    traffic_delay:     float = Field(default=0.0)
    predicted_delay_minutes: float = Field(default=0.0)
    cost_per_segment:  float = Field(default=0.0)
    road_type:         str
    delay_probability: float
    risk_level:        RiskLevel
    top_factors:       list[ShapFactor]
    geometry:          Optional[dict] = Field(default=None, description="GeoJSON LineString from OSRM")

    model_config = {"populate_by_name": True}


class ScoredRoute(BaseModel):
    route:              list[str]
    n_hops:             int
    total_distance_km:  float
    estimated_time_hr:  float
    mean_delay_risk:    float
    route_score:        float
    segments:           list[RouteSegment]


class RouteSummary(BaseModel):
    n_candidates:      int
    best_score:        float
    best_distance_km:  float
    best_time_hr:      float
    best_delay_risk:   float
    recommendation:    str


class RouteResponse(BaseModel):
    source:         str
    destination:    str
    departure_time: str
    best_route:     ScoredRoute
    alternatives:   list[ScoredRoute]
    summary:        RouteSummary


class FleetLeg(BaseModel):
    from_stop: str
    to_stop: str
    route: list[str]
    segments: list[RouteSegment]
    leg_score: float
    alternatives: list[ScoredRoute] = Field(default_factory=list)

class FleetPlan(BaseModel):
    visit_order: list[str]
    total_score: float
    total_distance_km: float
    total_estimated_time_hr: float
    legs: list[FleetLeg]

class FleetOptimizationResponse(BaseModel):
    source: str
    destinations: list[str]
    best_plan: FleetPlan
    alternatives: list[FleetPlan]


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status:       str
    model_loaded: bool
    model_name:   str
    graph_nodes:  int
    graph_edges:  int
    hubs:         list[str]
