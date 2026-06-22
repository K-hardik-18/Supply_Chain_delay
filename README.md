<p align="center">
  <h1 align="center">Smart Logistics Intelligence (SLI)</h1>
  <p align="center">
    <strong>AI-Powered Supply Chain Delay Prediction & Multi-Stop Route Optimization</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/XGBoost-2.0+-FF6600?logo=xgboost&logoColor=white" alt="XGBoost">
    <img src="https://img.shields.io/badge/Google_Maps-Directions_API-4285F4?logo=googlemaps&logoColor=white" alt="Google Maps">
    <img src="https://img.shields.io/badge/Visual_Crossing-Weather_API-green" alt="Visual Crossing">
    <img src="https://img.shields.io/badge/Leaflet.js-Maps-199900?logo=leaflet&logoColor=white" alt="Leaflet">
  </p>
</p>

---

## What Is This?

SLI is an end-to-end logistics platform that **predicts shipment delays** and **optimizes multi-stop delivery routes** across a 40-hub Indian logistics network. It combines ML classification/regression, live external APIs (weather, traffic, road routing), and a VRP (Vehicle Routing Problem) solver, all exposed through a FastAPI backend and an interactive Leaflet.js dashboard.

---

## Model Performance (Actual Metrics)

All numbers below are from `setup_and_run.py` on 50,000 synthetic shipments (seed=42), using a 70/15/15 train/val/test split (stratified).

### Classifier — Binary Delay Prediction

Three models are trained and compared. **XGBoost is auto-selected** based on highest ROC-AUC.

| Model               | ROC-AUC | PR-AUC | F1     | Accuracy | Precision | Recall | Threshold |
|----------------------|---------|--------|--------|----------|-----------|--------|-----------|
| Logistic Regression  | 0.9495  | 0.9247 | 0.8395 | 87.61%   | 0.8165    | 0.8638 | 0.55      |
| Random Forest        | 0.9626  | 0.9423 | 0.8654 | 89.79%   | 0.8558    | 0.8752 | 0.51      |
| **XGBoost (winner)** | **0.9669** | **0.9512** | **0.8720** | **90.36%** | **0.8685** | **0.8756** | **0.65** |

**XGBoost per-class breakdown (test set, n=7,500):**
| Class   | Precision | Recall | F1-Score | Support |
|---------|-----------|--------|----------|---------|
| On-time | 0.92      | 0.92   | 0.92     | 4,687   |
| Delayed | 0.87      | 0.88   | 0.87     | 2,813   |

- **Dataset delay rate:** 37.5% (18,753 out of 50,000)
- **Threshold tuning:** F1-maximized on validation set, swept over [0.25, 0.75] in 0.02 steps

### Regressor — Delay Minutes Prediction

| Metric | Value |
|--------|-------|
| Model  | XGBoost Regressor (150 trees, depth 6, lr 0.08) |
| Train / Test | 40,000 / 10,000 (80/20 split) |
| MAE    | **25.05 minutes** |
| RMSE   | **38.65 minutes** |
| R²     | **0.6981** |
| Mean target | 54.3 minutes |

---

## Feature Engineering

The model uses **25 features** across 6 categories. Training and inference use the exact same feature pipeline to prevent train/serve skew.

| Category | Features |
|----------|----------|
| **Route** | `distance_km`, `base_duration`, `traffic_time`, `traffic_delay`, `route_type_code`, `source_hub_type_code`, `dest_hub_type_code` |
| **Time** | `departure_hour`, `hour_sin`, `hour_cos`, `is_peak_hour`, `is_weekend`, `demand_pressure` |
| **Traffic** | `traffic_code`, `waiting_time_est` |
| **Weather** | `weather_code`, `temperature` |
| **Shipment** | `vehicle_code` (bike=0, van=1, truck=2), `cargo_code` (standard=0, perishable=1, fragile=2), `priority_level` (1–3), `hub_congestion` |
| **Interactions** | `traffic_x_peak`, `weather_x_distance`, `congestion_x_waiting`, `temp_x_cargo` |

SHAP (TreeExplainer) provides per-prediction feature importance, both as a summary plot and as live top-3 factors in the API response.

---

## Hub Network

**40 hubs** across India (North, West, South, East), forming a **fully-connected directed graph of 1,560 edges**. Hub types: `hub` (coded 1) and `warehouse` (coded 0). Capacities range from 100 to 600 shipments/day.

Distances are haversine-based for the static graph, overridden at inference time by **Google Maps Directions API** (if key provided) or **OSRM public API** for real road distances and durations.

---

## Route Optimization

### Scoring Formula

Each route segment is scored using a **normalized 4-factor composite**:

```
segment_score = 0.20 * (distance / 3000) + 0.40 * (time / 50) + 0.25 * delay_prob + 0.15 * (traffic_delay / 10)
```

| Weight | Factor | Normalization |
|--------|--------|---------------|
| 0.40   | Travel time (hours) | ÷ 50 hr max |
| 0.25   | ML delay probability | already 0–1 |
| 0.20   | Distance (km) | ÷ 3,000 km max |
| 0.15   | Traffic delay (hours) | ÷ 10 hr max |

Route-level delay risk = `1 - ∏(1 - p_i)` across segments.

### VRP Solver

- **≤3 destinations**: brute-force all permutations (≤6)
- **>3 destinations**: nearest-neighbor heuristic + reverse ordering
- Hub-and-spoke orderings are also evaluated (backtracking through origin)
- Legs are scored in parallel using `ThreadPoolExecutor` (4 workers)
- Max 6 destinations per request

### Candidate Paths

For each leg, `NetworkX.shortest_simple_paths(weight="distance_km")` generates up to 3 candidate paths through the graph. Each is fully scored by the ML model before the lowest-cost path is selected.

---

## External API Integration

| API | Purpose | Fallback |
|-----|---------|----------|
| **Google Maps Directions** | Road distance, duration, polyline geometry | OSRM public API → haversine + speed estimate |
| **Visual Crossing Weather** | Live weather condition + temperature for source city | Seasonal defaults (summer/monsoon/winter distributions) |
| **TomTom Traffic** | Real-time traffic delay ratio | Simulated traffic: 70% sim + 30% real hybrid blend |

All APIs are optional. The system operates fully offline using simulated fallbacks.

---

## Architecture

### Pipeline Flow

```
[User: source + up to 6 destinations]
              │
              ▼
     FastAPI Orchestrator (/predict-route)
              │
    ┌─────────┴──────────┐
    │ 1 dest             │ 2+ dests
    ▼                    ▼
  find_best_route()    optimize_fleet_route() [VRP]
    │                    │
    ▼                    ▼
  K shortest paths     Permutation orderings
  (NetworkX)           (brute-force or NN heuristic)
    │                    │
    └────────┬───────────┘
             ▼
  For each segment:
    ├─ Google Maps / OSRM → real distance & duration
    ├─ Visual Crossing → live weather
    ├─ TomTom → live traffic delay
    ├─ build_feature_vector() → 25 features
    ├─ XGBoost Classifier → delay probability
    ├─ XGBoost Regressor → predicted delay minutes
    ├─ SHAP TreeExplainer → top-3 risk factors
    └─ 4-factor normalized score
             │
             ▼
    SQLite auto-save (data/history.db)
             │
             ▼
    JSON response → Leaflet dashboard
```

### Data Pipeline (`setup_and_run.py`)

| Step | Action | Output |
|------|--------|--------|
| 1 | Generate 50K synthetic shipments | `data/simulated/shipments_raw.csv` (~10 MB) |
| 2 | Save hub and network definitions | `data/hubs.csv` (40 hubs), `data/network.csv` (1,560 edges) |
| 3 | Build 25-feature training matrix | `data/processed/train_features.csv` (~5 MB) |
| 4 | Train LR, RF, XGBoost classifiers; auto-select best by ROC-AUC | `models/delay_classifier.pkl` |
| 5 | Evaluate classifier on test set | `reports/evaluation_report.json`, `reports/confusion_matrix.png`, `reports/shap_summary.png` |
| 6 | Train XGBoost delay-minutes regressor | `models/delay_regressor.pkl`, `reports/regression_report.json` |

Total runtime: ~47 seconds.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Serves the HTML/JS/CSS dashboard |
| `GET`  | `/health` | Model + graph status check |
| `GET`  | `/hubs` | List all 40 hubs with lat/lon/type/capacity |
| `POST` | `/predict-delay` | Single-segment delay prediction with SHAP explanation |
| `POST` | `/optimize-route` | Score and rank candidate routes between two hubs |
| `POST` | `/predict-route` | Multi-destination fleet optimization (VRP solver) |
| `GET`  | `/history` | Paginated prediction + route history |
| `GET`  | `/analytics` | Aggregate analytics: risk distribution, hourly trends, riskiest corridors |
| `DELETE` | `/history` | Wipe all stored history |

Interactive docs at `/docs` (Swagger UI).

---

## Dashboard

The frontend (`frontend/`) is vanilla HTML/CSS/JS with Leaflet.js:

- **Light/Dark Theme Toggle** — swaps CSS variables and Carto map tiles
- **Multi-stop Input** — add up to 6 destination cities via dropdown
- **Delay Probability Gauge** — animated SVG arc showing ML risk percentage
- **SHAP Factors Panel** — top-3 features driving each prediction
- **Interactive Route Map** — Leaflet polylines with segment-level risk coloring and popup details
- **Analytics Dashboard** — hourly delay trends, riskiest corridors, risk distribution charts (powered by SQLite via `/analytics` API)

---

## Project Structure

```
Supply_chain /
├── frontend/
│   ├── index.html                # Dashboard layout
│   ├── style.css                 # Design system + dark/light themes
│   └── app.js                    # Leaflet map, API calls, charts
│
├── src/
│   ├── api/
│   │   ├── main.py               # FastAPI app, all endpoints
│   │   ├── schemas.py            # Pydantic request/response models
│   │   └── geocode.py            # Geocoding utilities
│   ├── features/
│   │   ├── build_training_features.py   # 25-feature contract definition
│   │   └── build_inference_features.py  # Live feature builder (mirrors training)
│   ├── models/
│   │   ├── train_classifier.py   # LR + RF + XGBoost training pipeline
│   │   ├── train_regressor.py    # XGBoost delay-minutes regressor
│   │   ├── evaluate.py           # Test-set evaluation + confusion matrix + SHAP plot
│   │   ├── predict.py            # Model loading + inference (classifier + regressor)
│   │   └── explain.py            # Per-prediction SHAP explanations
│   ├── routing/
│   │   ├── graph_builder.py      # NetworkX DiGraph from network.csv
│   │   ├── optimizer.py          # K-shortest paths candidate generator
│   │   ├── scorer.py             # 4-factor normalized route scoring
│   │   └── vrp.py                # Multi-stop VRP solver (parallel)
│   ├── pipeline/
│   │   └── orchestrator.py       # Single/multi-dest dispatch controller
│   ├── simulator/
│   │   ├── generator.py          # 50K synthetic shipment generator
│   │   ├── hubs.py               # 40-hub definitions (lat/lon/type/capacity)
│   │   ├── network.py            # Pairwise edge generation (haversine)
│   │   ├── traffic.py            # Traffic sampling (peak/offpeak/weekend)
│   │   ├── weather.py            # Weather sampling (summer/monsoon/winter)
│   │   └── shipments.py          # Vehicle/cargo/priority sampling
│   ├── db/
│   │   └── history.py            # SQLite prediction + route persistence
│   └── utils/
│       ├── googlemaps_api.py     # Google Maps Directions integration
│       ├── osrm_api.py           # OSRM public API fallback
│       └── traffic_api.py        # TomTom traffic delay conversion
│
├── configs/config.yaml           # All hyperparameters and scoring weights
├── models/                       # Saved .pkl model bundles
├── data/                         # Simulated + processed CSVs, SQLite DB
├── reports/                      # JSON reports, confusion matrix, SHAP plot
├── requirements.txt              # Python dependencies
├── setup_and_run.py              # One-shot pipeline runner
└── .env                          # API keys (not committed)
```

---

## Quick Start

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
GOOGLE_MAPS_API_KEY=your_key_here       # Road routing + polylines
VISUAL_CROSSING_API_KEY=your_key_here   # Live weather
TOMTOM_API_KEY=your_key_here            # Real-time traffic
```

All three are optional — the system works fully offline using simulated fallbacks.

### 3. Generate Data & Train Models

```bash
python setup_and_run.py
```

Generates 50K shipments, trains 3 classifiers + 1 regressor, auto-selects the best model, and saves all reports. Takes ~47 seconds.

### 4. Start the Application

```bash
uvicorn src.api.main:app --port 8080 --reload --reload-dir src --reload-dir frontend
```

Open **[http://localhost:8080](http://localhost:8080)** in your browser.

---

## XGBoost Classifier Hyperparameters

| Parameter | Value |
|-----------|-------|
| `n_estimators` | 400 (early-stopped at ~178) |
| `max_depth` | 5 |
| `learning_rate` | 0.05 |
| `subsample` | 0.80 |
| `colsample_bytree` | 0.80 |
| `min_child_weight` | 3 |
| `gamma` | 0.1 |
| `reg_alpha` | 0.1 |
| `reg_lambda` | 1.0 |
| `scale_pos_weight` | 2.3 |
| `eval_metric` | aucpr |
| `early_stopping_rounds` | 30 |

---

## Key Design Decisions

- **Synthetic data with latent interaction rules**: delay labels come from non-trivial feature interactions (e.g., `weather × distance`, `bike + long route`, `storm at peak hour`), not simple thresholds. No single feature can perfectly predict the label.
- **Threshold tuning**: the classification threshold is F1-optimized per model, not fixed at 0.5. XGBoost's optimal threshold of 0.65 reflects the class imbalance handling.
- **Training/serving parity**: `build_training_features.py` defines the canonical 25-feature contract; `build_inference_features.py` replicates it exactly for live predictions.
- **Hybrid traffic blending**: inference uses 70% simulated + 30% live traffic to avoid distribution shift from the training data.

---

<p align="center">
  <sub>Engineered by <strong>Hardik Kumawat</strong> · <strong>Vardhan Bhati</strong> · <strong>Harshvardhan Sharma</strong></sub>
</p>
