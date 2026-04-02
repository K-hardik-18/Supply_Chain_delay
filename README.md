<p align="center">
  <h1 align="center">🚚 Smart Logistics Intelligence (SLI)</h1>
  <p align="center">
    <strong>AI-Powered Supply Chain Delay Prediction & Multi-Stop Route Optimization Platform</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/XGBoost-2.0+-FF6600?logo=xgboost&logoColor=white" alt="XGBoost">
    <img src="https://img.shields.io/badge/SHAP-Explainability-blueviolet" alt="SHAP">
    <img src="https://img.shields.io/badge/OSRM-Routing-green" alt="OSRM">
    <img src="https://img.shields.io/badge/Leaflet.js-Maps-199900?logo=leaflet&logoColor=white" alt="Leaflet">
  </p>
</p>

---

## 🎯 What Is This?

SLI is an end-to-end logistics intelligence platform that predicts **shipment delays** and finds the **optimal multi-stop delivery route** across 40 hubs in India. It combines:

- **Dual-Model ML Pipeline** — XGBoost Classifier (delay probability) + XGBoost Regressor (delay minutes)
- **VRP Solver** — Traveling Salesperson Problem with parallelized scoring and nearest-neighbor heuristic
- **4-Factor Route Scoring** — Balances distance, time, delay risk, and traffic conditions
- **Real-Time APIs** — Live weather (OpenWeatherMap), traffic (TomTom), and road geometry (OSRM)
- **SHAP Explainability** — Game-theoretic explanations for every prediction
- **Modern Web Dashboard** — Dark glassmorphism UI with interactive maps, gauges, and route visualization

---

## 🖥️ Dashboard Preview

The dashboard features a dark-themed glassmorphism design with:
- **Delay Probability Gauge** — Animated arc showing risk percentage
- **Probabilistic Delay Estimate** — Displayed as `T ± t` with propagated uncertainty
- **SHAP Feature Importance** — Top factors driving the prediction
- **Interactive Leaflet Map** — Real OSRM road geometries with color-coded risk markers
- **Route Optimization Panel** — Leg-by-leg breakdown with scores, distances, and alternatives

---

## 📁 Project Structure

```
SLI/
├── frontend/                        # Web Dashboard (Vanilla HTML/CSS/JS)
│   ├── index.html                   # Main dashboard layout with glassmorphism UI
│   ├── style.css                    # Design system (CSS variables, gradients, animations)
│   └── app.js                       # Frontend logic — API calls, map rendering, dynamic results
│
├── src/                             # Backend Source Code
│   ├── api/
│   │   ├── main.py                  # FastAPI server — endpoints, static file serving, lifespan
│   │   └── schemas.py               # Pydantic request/response models with strict validation
│   │
│   ├── models/
│   │   ├── train_classifier.py      # Trains LR, RF, XGBoost classifiers — auto-selects best
│   │   ├── train_regressor.py       # Trains XGBRegressor for delay minute prediction
│   │   ├── predict.py               # Dual-model inference (classifier + regressor)
│   │   ├── explain.py               # SHAP TreeExplainer with human-readable feature labels
│   │   └── evaluate.py              # Model comparison and evaluation metrics
│   │
│   ├── pipeline/
│   │   └── orchestrator.py          # Master controller — routes single-hop vs multi-stop VRP
│   │
│   ├── routing/
│   │   ├── graph_builder.py         # Builds NetworkX digraph (40 nodes, 1560 edges)
│   │   ├── optimizer.py             # Generates K-shortest candidate paths, scores each
│   │   ├── scorer.py                # 4-factor cost function per route segment
│   │   └── vrp.py                   # Parallelized VRP solver with nearest-neighbor heuristic
│   │
│   ├── features/
│   │   ├── build_training_features.py   # Batch feature engineering for model training
│   │   └── build_inference_features.py  # Real-time feature vector construction with caching
│   │
│   ├── simulator/
│   │   ├── generator.py             # Generates 50,000 synthetic shipments for training
│   │   ├── hubs.py                  # 40 Indian logistics hubs with GPS coordinates
│   │   ├── network.py               # Builds fully-connected hub network (1560 edges)
│   │   ├── traffic.py               # Traffic simulation (peak/off-peak/weekend patterns)
│   │   ├── weather.py               # Weather fallback + OpenWeatherMap live API with caching
│   │   └── shipments.py             # Vehicle/cargo type encoders
│   │
│   ├── db/
│   │   └── history.py               # SQLite prediction/route history logging
│   │
│   └── utils/
│       ├── osrm_api.py              # OSRM public API client with LRU cache (no key needed)
│       └── traffic_api.py           # TomTom traffic delay API client
│
├── configs/
│   └── config.yaml                  # Hyperparameters, weights, thresholds, simulation config
│
├── data/
│   ├── simulated/                   # Raw synthetic shipment CSVs
│   ├── processed/                   # Training-ready feature matrices
│   ├── hubs.csv                     # Hub reference data
│   └── network.csv                  # Edge reference data
│
├── models/
│   ├── delay_classifier.pkl         # Trained XGBoost classifier bundle
│   └── delay_regressor.pkl          # Trained XGBoost regressor bundle
│
├── reports/
│   ├── confusion_matrix.png         # Model evaluation visualization
│   ├── shap_summary.png             # SHAP feature importance plot
│   ├── evaluation_report.json       # Precision, recall, F1 metrics
│   └── model_comparison.json        # Multi-model benchmark results
│
├── setup_and_run.py                 # One-shot pipeline: simulate → train → evaluate
├── requirements.txt                 # Python dependencies
├── .env                             # API keys (not committed — see setup below)
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip

### 1. Clone & Install

```bash
git clone https://github.com/K-hardik-18/Supply_Chain_delay.git
cd Supply_Chain_delay
pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)

Create a `.env` file in the project root:

```env
OPENWEATHER_API_KEY=your_key_here     # Free at https://openweathermap.org/api
TOMTOM_API_KEY=your_key_here          # Free at https://developer.tomtom.com
```

> **Note:** Both keys are optional. Without them, the system uses intelligent simulated fallbacks. The OSRM routing API is completely free and requires no key.

### 3. Generate Data & Train Models

```bash
python setup_and_run.py
```

This script automatically:
1. Generates 50,000 synthetic shipment records
2. Builds training feature matrices
3. Trains and compares 3 ML models (Logistic Regression, Random Forest, XGBoost)
4. Saves the best-performing model to `models/`
5. Outputs evaluation reports and SHAP visualizations to `reports/`

### 4. Start the Server

```bash
uvicorn src.api.main:app --port 8080 --reload --reload-dir src --reload-dir frontend
```

### 5. Open the Dashboard

Navigate to **[http://localhost:8080](http://localhost:8080)** in your browser.

---

## ⚙️ How It Works

### End-to-End Request Flow

```
User clicks "Run Analysis"
        │
        ▼
  POST /predict-route
        │
        ▼
  ┌─────────────────┐
  │   Orchestrator   │ ← Detects single-hop vs multi-stop
  └────────┬────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
  Optimizer    VRP Solver
  (1 dest)    (2+ dests)
     │           │
     ▼           ▼
  ┌──────────────────┐
  │  Route Scorer    │ ← Per-segment cost calculation
  │  (4-Factor)      │
  └────────┬─────────┘
           │
  ┌────────┴────────────────────────┐
  │  For each segment:              │
  │  1. OSRM API → road distance   │
  │  2. Weather API → conditions   │
  │  3. Traffic API → congestion   │
  │  4. Feature Vector → XGBoost   │
  │  5. SHAP → explanation         │
  └────────┬────────────────────────┘
           │
           ▼
  Best route + alternatives
  returned to dashboard
```

### 4-Factor Scoring Formula

```
cost = 0.01 × distance_km
     + 0.50 × total_expected_time
     + 0.30 × delay_probability
     + 0.19 × traffic_delay
```

The route with the **lowest composite score** wins. Alternative routes are preserved and shown in collapsible accordions.

### Delay Estimation Display

Delays are shown as **`T ± t`** using propagated uncertainty:
- **T** = predicted delay minutes from XGBoost Regressor
- **t** = uncertainty margin (10–25% of T, minimum 1 minute)
- **< 5 min** results display as *"Minimal Delay Expected"* to avoid misleading noise
- Multi-stop routes aggregate using **quadrature error propagation**: `σ_total = √(σ₁² + σ₂² + ...)`

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the web dashboard |
| `GET` | `/health` | Health check with model/graph status |
| `GET` | `/hubs` | Returns all 40 hubs with coordinates |
| `POST` | `/predict-route` | Main analysis endpoint (single or multi-stop) |
| `GET` | `/history` | Recent prediction history |
| `GET` | `/analytics` | Aggregate analytics and trends |
| `GET` | `/docs` | Auto-generated Swagger API docs |

### Example Request

```json
POST /predict-route
{
  "source": "Delhi (Hub)",
  "destinations": ["Jaipur (Hub)", "Ahmedabad (Hub)"],
  "departure_time": "2026-04-02T14:00:00",
  "vehicle_type": "van",
  "cargo_type": "standard",
  "priority_level": 2
}
```

---

## 🧠 ML Architecture

### Dual-Model Pipeline

| Model | Task | Output |
|-------|------|--------|
| **XGBoost Classifier** | Delay risk classification | Probability (0–1) |
| **XGBoost Regressor** | Delay magnitude estimation | Minutes of delay |

### Feature Set (20 features)

| Category | Features |
|----------|----------|
| **Route** | `distance_km`, `route_type_code` |
| **Hub** | `source_hub_type_code`, `dest_hub_type_code`, `hub_congestion` |
| **Time** | `departure_hour`, `hour_sin`, `hour_cos`, `is_peak_hour`, `is_weekend` |
| **Traffic** | `traffic_code`, `traffic_time`, `traffic_delay`, `waiting_time_est`, `demand_pressure` |
| **Weather** | `weather_code`, `temperature` |
| **Shipment** | `vehicle_code`, `cargo_code`, `priority_level` |
| **Interaction** | `traffic_x_peak`, `weather_x_distance`, `congestion_x_waiting`, `temp_x_cargo` |

---

## 🏎️ Performance Optimizations

| Optimization | Impact |
|-------------|--------|
| **Parallel leg scoring** | ThreadPoolExecutor (4 workers) scores VRP legs concurrently |
| **Nearest-neighbor heuristic** | Avoids N! brute-force for > 3 destinations |
| **OSRM LRU cache** (1024 entries) | Eliminates duplicate road API calls |
| **Feature vector cache** | Same inputs return cached DataFrames instantly |
| **Weather response cache** | One API call per city per session |
| **Reduced candidates** | 3 candidate paths per leg (down from 5) |

---

## 📊 Reports

After running `setup_and_run.py`, evaluation outputs are saved to `reports/`:

- `confusion_matrix.png` — Visual classification performance
- `shap_summary.png` — Global feature importance via SHAP
- `evaluation_report.json` — Precision, Recall, F1-Score
- `model_comparison.json` — Head-to-head model benchmarks

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **ML** | XGBoost, Scikit-Learn, SHAP |
| **Backend** | FastAPI, Pydantic, Uvicorn |
| **Routing** | NetworkX, OSRM Public API |
| **Frontend** | Vanilla HTML/CSS/JS, Leaflet.js |
| **APIs** | OpenWeatherMap, TomTom Traffic |
| **Data** | Pandas, NumPy, SQLite |

---

## 👥 Authors

**Hardik Kumawat** · **Vardhan Bhati** · **Harshvardhan Sharma**

---

<p align="center">
  <sub>Built with ❤️ using Python, XGBoost, and FastAPI</sub>
</p>
