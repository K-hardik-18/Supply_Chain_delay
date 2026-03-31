"""
streamlit_app.py  —  Smart Logistics Intelligence dashboard.

Run:
    streamlit run app/streamlit_app.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import httpx
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import calendar

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="Smart Logistics Intelligence",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .risk-low       { color: #1D9E75; font-weight: 600; }
    .risk-medium    { color: #EF9F27; font-weight: 600; }
    .risk-high      { color: #D85A30; font-weight: 600; }
    .risk-very_high { color: #A32D2D; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ── Example scenarios ─────────────────────────────────────────────────────────

EXAMPLES = {
    "— manual entry —": None,
    "🟢 Low risk — short, off-peak, clear": {
        "source": "Jaipur", "destination": "Ajmer",
        "hour": 14, "month": 1,
        "vehicle_type": "van", "cargo_type": "standard", "priority_level": 2,
        "note": "125 km regional, 2pm afternoon, winter clear weather. Expect < 10% delay.",
    },
    "🟡 Medium risk — peak hour, highway": {
        "source": "Delhi", "destination": "Agra",
        "hour": 8, "month": 11,
        "vehicle_type": "truck", "cargo_type": "standard", "priority_level": 2,
        "note": "200 km highway, 8am peak, November — fog possible. Moderate risk.",
    },
    "🔴 High risk — monsoon, peak, perishable": {
        "source": "Jaipur", "destination": "Lucknow",
        "hour": 8, "month": 7,
        "vehicle_type": "bike", "cargo_type": "perishable", "priority_level": 3,
        "note": "512 km, monsoon rain, 8am peak, bike + perishable. Expect 80%+ delay.",
    },
    "🔴 Very high — long haul, storm, peak": {
        "source": "Jodhpur", "destination": "Varanasi",
        "hour": 17, "month": 7,
        "vehicle_type": "bike", "cargo_type": "perishable", "priority_level": 3,
        "note": "1000+ km, monsoon storm, 5pm peak, worst-case combination. Near 100%.",
    },
    "🔴 High risk — fog, fragile, long": {
        "source": "Amritsar", "destination": "Agra",
        "hour": 8, "month": 1,
        "vehicle_type": "bike", "cargo_type": "fragile", "priority_level": 3,
        "note": "580 km, winter fog, bike carrying fragile cargo at morning peak.",
    },
}


# ── API helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_hubs() -> list[str]:
    try:
        r = httpx.get(f"{API_BASE}/hubs", timeout=5)
        return sorted(r.json()["hubs"])
    except Exception:
        return [
            "Agra","Ajmer","Amritsar","Bikaner","Chandigarh","Delhi","Gurgaon",
            "Haridwar","Jaipur","Jodhpur","Kanpur","Kota","Lucknow","Ludhiana",
            "Mathura","Meerut","Noida","Prayagraj","Udaipur","Varanasi",
        ]


@st.cache_data(ttl=60)
def fetch_health() -> dict | None:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        return r.json()
    except Exception:
        return None


def call_predict(payload: dict) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}/predict-delay", json=payload, timeout=20)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.json().get('detail', str(e))}")
    except Exception as e:
        st.error(f"Cannot reach API at {API_BASE}. Is it running?\n`uvicorn src.api.main:app --reload --port 8000`\n\nError: {e}")
    return None


def call_optimize(payload: dict) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}/optimize-route", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.json().get('detail', str(e))}")
    except Exception as e:
        st.error(f"Route optimization failed: {e}")
    return None


# ── Visualisation helpers ─────────────────────────────────────────────────────

RISK_COLOUR = {
    "low":       "#1D9E75",
    "medium":    "#EF9F27",
    "high":      "#D85A30",
    "very_high": "#A32D2D",
}


def risk_badge(level: str) -> str:
    c = RISK_COLOUR.get(level, "#888")
    return f'<span style="color:{c};font-weight:700;font-size:1.1rem">{level.replace("_"," ").upper()}</span>'


def delay_gauge(prob: float) -> go.Figure:
    pct = round(prob * 100, 1)
    colour = (
        "#1D9E75" if prob < 0.25 else
        "#EF9F27" if prob < 0.50 else
        "#D85A30" if prob < 0.70 else
        "#A32D2D"
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 42, "color": colour}},
        gauge={
            "axis": {"range": [0, 100], "ticksuffix": "%", "tickfont": {"size": 11}},
            "bar":  {"color": colour, "thickness": 0.28},
            "steps": [
                {"range": [0,  25], "color": "#E1F5EE"},
                {"range": [25, 50], "color": "#FAEEDA"},
                {"range": [50, 70], "color": "#FAECE7"},
                {"range": [70,100], "color": "#FCEBEB"},
            ],
            "threshold": {"line": {"color": colour, "width": 3}, "value": pct},
        },
        title={"text": "Delay Probability", "font": {"size": 15}},
    ))
    fig.update_layout(height=230, margin=dict(t=50, b=0, l=20, r=20))
    return fig


def shap_bar(factors: list[dict]) -> go.Figure:
    labels  = [f["label"] for f in factors]
    values  = [f["shap_value"] for f in factors]
    colours = [RISK_COLOUR["high"] if v > 0 else RISK_COLOUR["low"] for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colours,
        text=[f"{v:+.3f}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        title="Top contributing factors (SHAP)",
        height=200, margin=dict(t=40, b=20, l=10, r=70),
        xaxis=dict(title="SHAP value  (+ve = more delay risk)"),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )
    return fig


def route_comparison_bar(routes: list[dict]) -> go.Figure:
    labels  = [" → ".join(r["route"]) for r in routes]
    scores  = [r["route_score"] for r in routes]
    colours = ["#1D9E75" if i == 0 else "#378ADD" for i in range(len(routes))]
    fig = go.Figure(go.Bar(
        x=labels, y=scores,
        marker_color=colours,
        text=[f"{s:.3f}" for s in scores],
        textposition="outside",
    ))
    fig.update_layout(
        title="Route comparison — composite score (lower = better)",
        height=300, margin=dict(t=40, b=80, l=10, r=10),
        yaxis=dict(title="Route score"),
        xaxis=dict(tickangle=-25),
    )
    return fig


def segment_risk_chart(segments: list[dict]) -> go.Figure:
    labels = [f"{s['from']} → {s['to']}" for s in segments]
    probs  = [s["delay_probability"] for s in segments]
    cols   = [RISK_COLOUR.get(s["risk_level"], "#888") for s in segments]
    fig = go.Figure(go.Bar(
        x=labels, y=probs,
        marker_color=cols,
        text=[f"{p:.0%}" for p in probs],
        textposition="outside",
    ))
    fig.update_layout(
        title="Per-segment delay risk",
        height=260, margin=dict(t=40, b=10, l=10, r=10),
        yaxis=dict(title="Delay probability", tickformat=".0%", range=[0, 1.15]),
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("🚚 Smart Logistics")
st.sidebar.caption("Multi-model delay prediction & ML route optimization")
st.sidebar.divider()

# Show active model info
health = fetch_health()
if health:
    model_name = health.get("model_name", "unknown").replace("_", " ").title()
    st.sidebar.success(f"🤖 Active model: **{model_name}**")

hubs = fetch_hubs()

# Example scenario loader
st.sidebar.subheader("Quick examples")
selected_example = st.sidebar.selectbox("Load a scenario", list(EXAMPLES.keys()), index=0)

if EXAMPLES[selected_example] is not None:
    ex = EXAMPLES[selected_example]
    default_src   = ex["source"]
    default_dst   = ex["destination"]
    default_hour  = ex["hour"]
    default_month = ex["month"]
    default_veh   = ex["vehicle_type"]
    default_cargo = ex["cargo_type"]
    default_pri   = ex["priority_level"]
    st.sidebar.info(ex["note"])
else:
    now           = datetime.now()
    default_src   = "Jaipur"
    default_dst   = "Ajmer"
    default_hour  = now.hour
    default_month = now.month
    default_veh   = "van"
    default_cargo = "standard"
    default_pri   = 2

st.sidebar.divider()
st.sidebar.subheader("Shipment details")

source = st.sidebar.selectbox(
    "Origin hub", hubs,
    index=hubs.index(default_src) if default_src in hubs else 0,
    key=f"src_{selected_example}",
)
dst_options     = [h for h in hubs if h != source]
dst_default_idx = dst_options.index(default_dst) if default_dst in dst_options else 0
destination     = st.sidebar.selectbox(
    "Destination hub", dst_options, index=dst_default_idx,
    key=f"dst_{selected_example}",
)

# ── Departure time ────────────────────────────────────────────────────────────
st.sidebar.markdown("**Departure time**")

default_day  = 15
default_date = datetime(2024, default_month, default_day).date()

dep_date = st.sidebar.date_input(
    "Departure date", value=default_date,
    key=f"date_{selected_example}",
)

dep_hour = st.sidebar.slider(
    "Hour of day",
    min_value=0, max_value=23,
    value=default_hour,
    help="Peak hours: 7–9 am and 5–7 pm (highest delay risk)",
    key=f"hour_{selected_example}",
)

hour_label = f"{dep_hour:02d}:00  "
if dep_hour in [7, 8, 9, 17, 18, 19]:
    hour_label += "⚠️ peak hour"
elif 0 <= dep_hour <= 5:
    hour_label += "🌙 night"
else:
    hour_label += "✅ off-peak"
st.sidebar.caption(f"Departure: **{dep_date}** at **{hour_label}**")

dep_dt_str = f"{dep_date}T{dep_hour:02d}:00:00"

vehicle_type = st.sidebar.selectbox(
    "Vehicle type", ["van", "truck", "bike"],
    index=["van", "truck", "bike"].index(default_veh),
    key=f"veh_{selected_example}",
)
cargo_type = st.sidebar.selectbox(
    "Cargo type", ["standard", "perishable", "fragile"],
    index=["standard", "perishable", "fragile"].index(default_cargo),
    key=f"cargo_{selected_example}",
)
priority_level = st.sidebar.selectbox(
    "Priority level", [1, 2, 3],
    index=[1, 2, 3].index(default_pri),
    key=f"pri_{selected_example}",
)

st.sidebar.divider()
run_btn = st.sidebar.button("▶ Run Analysis", type="primary", use_container_width=True)

payload = {
    "source":          source,
    "destination":     destination,
    "departure_time":  dep_dt_str,
    "vehicle_type":    vehicle_type,
    "cargo_type":      cargo_type,
    "priority_level":  priority_level,
}


# ── Main panel ────────────────────────────────────────────────────────────────

st.title("Smart Logistics Intelligence")
st.caption(
    "Multi-model delay prediction (LR / RF / XGBoost) with SHAP explainability "
    "and 3-factor ML-scored graph routing (time + delay risk + distance)."
)

with st.expander("ℹ️ What drives high delay risk?", expanded=False):
    st.markdown("""
| Factor | Low risk | High risk |
|---|---|---|
| **Departure hour** | 10 am – 4 pm | 7–9 am or 5–7 pm (peak) |
| **Season / month** | Winter (Jan–Feb, clear) | Monsoon (Jun–Sep, rain/storm) |
| **Distance** | < 150 km | > 400 km |
| **Vehicle** | Truck or van | Bike on long routes |
| **Cargo** | Standard | Perishable or fragile |

Try the **Quick examples** dropdown in the sidebar to see high-risk scenarios instantly.
""")

with st.expander("📊 Route scoring formula", expanded=False):
    st.markdown("""
Routes are scored using a **3-factor composite**:

```
score = 0.35 × normalized_time + 0.40 × delay_risk + 0.25 × normalized_distance
```

- **Delay risk** has the highest weight → risky routes are penalized
- **Travel time** matters more than raw distance → faster routes preferred
- **Shortest distance is NOT always chosen** — fastest + safest wins
""")

if not run_btn:
    st.info("Configure your shipment in the sidebar and click **▶ Run Analysis**.")
    st.stop()

col_pred, col_route = st.columns([1, 2])

# ── Left: Delay prediction ────────────────────────────────────────────────────
with col_pred:
    st.subheader("Delay Prediction")
    with st.spinner("Predicting..."):
        pred = call_predict(payload)

    if pred:
        st.plotly_chart(delay_gauge(pred["delay_probability"]), use_container_width=True)

        verdict = "⚠️ Likely delayed" if pred["delayed"] else "✅ Likely on time"
        st.markdown(f"**Prediction:** {verdict}")
        st.markdown(f"**Risk level:** {risk_badge(pred['risk_level'])}", unsafe_allow_html=True)

        ctx = pred["context"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Distance",    f"{ctx['distance_km']} km")
        c2.metric("Traffic",     ctx["traffic_level"].title())
        c3.metric("Weather",     ctx["weather"].title())
        c4, c5 = st.columns(2)
        c4.metric("Temperature", f"{ctx['temperature']} °C")
        c5.metric("Est. wait",   f"{ctx['waiting_min']} min")

        st.divider()
        st.subheader("Why this prediction?")
        st.plotly_chart(shap_bar(pred["top_factors"]), use_container_width=True)

        with st.expander("Full factor breakdown"):
            rows = [{
                "Feature":   f["label"],
                "Value":     f["value"],
                "SHAP":      f["shap_value"],
                "Direction": "↑ Adds risk" if f["direction"] == "increases_risk" else "↓ Reduces risk",
            } for f in pred["top_factors"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Right: Route optimization ─────────────────────────────────────────────────
with col_route:
    st.subheader("Route Optimization")
    with st.spinner("Scoring routes..."):
        opt = call_optimize(payload)

    if opt:
        best       = opt["best_route"]
        all_routes = [opt["best_route"]] + opt["alternatives"]

        _route_str = ' → '.join(best['route'])
        _hop_str   = 'direct' if best['n_hops'] == 0 else str(best['n_hops']) + ' stop(s)'
        _risk_str  = str(round(best['mean_delay_risk'] * 100)) + '%'
        _time_str  = f"~{best.get('estimated_time_hr', '?')} hr"
        st.success(
            f'📍 **Best route:** {_route_str} ({_hop_str}) — '
            f'{best["total_distance_km"]} km · {_time_str} · {_risk_str} avg delay risk'
        )

        st.plotly_chart(route_comparison_bar(all_routes), use_container_width=True)

        st.subheader("Best route — segment breakdown")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total distance", f"{best['total_distance_km']} km")
        m2.metric("Est. time",      f"{best.get('estimated_time_hr', '?')} hr")
        m3.metric("Avg delay risk", f"{best['mean_delay_risk']:.0%}")
        m4.metric("Route score",    f"{best['route_score']:.3f}")

        st.plotly_chart(segment_risk_chart(best["segments"]), use_container_width=True)

        for seg in best["segments"]:
            _seg_time = f" · ~{seg.get('estimated_time_hr', '?')} hr" if seg.get('estimated_time_hr') else ""
            with st.expander(
                f"**{seg['from']} → {seg['to']}** — "
                f"{seg['distance_km']} km{_seg_time} · "
                f"{seg['delay_probability']:.0%} risk · "
                f"{seg['road_type'].title()} road"
            ):
                st.markdown(f"**Risk:** {risk_badge(seg['risk_level'])}", unsafe_allow_html=True)
                df = pd.DataFrame([{
                    "Factor":    f["label"],
                    "Value":     f["value"],
                    "SHAP":      f["shap_value"],
                    "Direction": "↑ Risk" if f["direction"] == "increases_risk" else "↓ Risk",
                } for f in seg["top_factors"]])
                st.dataframe(df, use_container_width=True, hide_index=True)

        if opt["alternatives"]:
            st.divider()
            st.subheader(f"Alternatives ({len(opt['alternatives'])} routes)")
            for i, alt in enumerate(opt["alternatives"], 1):
                delta = alt["route_score"] - best["route_score"]
                _alt_time = f" · ~{alt.get('estimated_time_hr', '?')} hr" if alt.get('estimated_time_hr') else ""
                with st.expander(
                    f"Alt {i}: {' → '.join(alt['route'])} — "
                    f"score {alt['route_score']:.3f} (+{delta:.3f} vs best)"
                ):
                    a1, a2, a3, a4 = st.columns(4)
                    a1.metric("Distance",   f"{alt['total_distance_km']} km")
                    a2.metric("Est. time",  f"{alt.get('estimated_time_hr', '?')} hr")
                    a3.metric("Delay risk", f"{alt['mean_delay_risk']:.0%}")
                    a4.metric("Score",      f"{alt['route_score']:.3f}")