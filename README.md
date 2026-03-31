# 🚚 Smart Logistics Intelligence (SLI)

**AI-powered Multi-Stop Fleet Optimization, Delay Prediction, and Route Explainability Platform.**

Combines multi-model machine learning (XGBoost), graph-based Operations Research (Traveling Salesperson Problem), real-time weather/traffic APIs, geometric road mapping (OSRM), and SHAP explainability — all served through a blazingly fast modern web dashboard.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Multi-Model ML** | Trains Logistic Regression, Random Forest, and dual-XGBoost pipelines — auto-selects the best model predicting BOTH Delay Probability and exact Delay Minutes. |
| **VRP TSP Engine** | Solves the Traveling Salesperson Problem using exact sequence permutations to perfectly route multi-stop deliveries. |
| **4-Factor Route Scoring** | `cost = w1×distance + w2×total_expected_time + w3×delay_probability + w4×traffic_delay` — actively evaluates if detouring through longer geography is mathematically faster. |
| **Intelligent Pipeline** | Native `orchestrator.py` intercepts route requests detecting A->B dispatch vs full Fleet VRP sequences seamlessly. |
| **SHAP Explainability** | Every delay prediction includes top contributing mathematical factors via Game Theory (TreeSHAP). |
| **Real-Time APIs** | OpenWeatherMap (live weather) + TomTom (traffic) + OSRM Public API (real geometric road distances and poly-lines). |
| **Graph Routing** | NetworkX mathematical digraph with exactly **40 strict Hubs/Warehouses** and **1,560 directed edges** for perfect pathfinding. |
| **Web Dashboard** | Clean glassmorphism frontend mapped with Leaflet.js, featuring dynamically computed **probabilistic delay margins**, interactive collapsible Alternative Route accordions, and pure mathematical scores. |

---

## 📁 Extreme File Structure & Deep Explanations

Here is a comprehensive breakdown of every file driving this platform and exactly what it does at the extreme ends of the application.

```
SLI/
├── frontend/                    # Standalone web frontend (The User Interface)
│   ├── index.html               # Main Dashboard page. Defines the dark glassmorphism UI layout, native <select> Hub dropdowns, Leaflet map containers, and the result cards.
│   ├── style.css                # CSS Variables and design system (gradients, animations, glass cards).
│   └── app.js                   # The crucial Javascript brain. Awaits the API Hub configuration, binds user inputs, synthetic prediction gauges, parses the massive VRP API payloads, dynamically renders the Leaflet road geometries, and lists the Alternative discarded sequences.
│
├── src/                         # Core Backend Source Code
│   ├── api/                     # FastAPI Application Layer
│   │   ├── main.py              # The web server engine. Exposes the endpoints like `/health`, `/hubs`, and the unified `/predict-route` Orchestrator endpoint.
│   │   └── schemas.py           # Strictly-typed Pydantic JSON validation rules. Guarantees that the data moving between the frontend and the Python backend correctly maps est_delay and costs.
│   │
│   ├── models/                  # Machine Learning Training & Inference
│   │   ├── train_classifier.py  # Builds and trains classification models against historical synthetics data to predict probability of delay.
│   │   ├── train_regressor.py   # Builds and trains the XGBRegressor pipeline to predict the absolute number of minutes a shipment will be delayed.
│   │   ├── predict.py           # Loads the winning model double-bundle (`.pkl`) into RAM and runs fast dual-inference natively feeding scoring loops.
│   │   ├── explain.py           # Executes TreeSHAP calculations to mathematically explain exactly which features caused a delay risk to spike.
│   │   └── evaluate.py          # Grading mechanism the system uses to pick the absolute best ML model out of the candidates.
│   │
│   ├── pipeline/                # Global Logic Controllers
│   │   └── orchestrator.py      # The Master Endpoint controller natively managing 1-to-1 optimization limits vs massive multi-stop fleet permutations under one API Roof.
│   │
│   ├── routing/                 # Operations Research & Mathematical Pathfinding
│   │   ├── graph_builder.py     # Reads `network.csv` and builds the NetworkX mathematical memory structure in RAM used by all subsequent graph algorithms.
│   │   ├── candidate_routes.py  # Uses Yen's K-Shortest Paths to generate topological detours (e.g., Candidates 1 to 5) between any two hubs in India.
│   │   ├── scorer.py            # Converts OSRM driving duration, actual Distance, and XGBoost Delay Risk into a single massive normalized 'Composite Penalty Score'. The lowest score wins.
│   │   ├── optimizer.py         # The middleman orchestrator. Takes Origin and Destination, grabs the 5 NetworkX candidate paths, throws them into the `scorer.py`, and returns only the ultimate mathematical winner.
│   │   └── vrp.py               # The Crown Jewel. Takes 3+ destinations, runs combinatorial permutations (`itertools`) to evaluate every possible sequence, scores them using the `optimizer.py`, and saves discarded "losers" to an `alternatives` array payload.
│   │
│   ├── features/                # Feature Engineering Pipeline
│   │   ├── build_training_features.py   # Large-scale, batch processing to convert historical string data into pure mathematics for model training.
│   │   └── build_inference_features.py  # The live data pipe. When the UI asks for a route, it pings the OSRM, Weather, and Traffic APIs here to construct an exact vector snapshot of current conditions before hitting XGBoost.
│   │
│   ├── simulator/               # Database Engine & Generators
│   │   ├── generator.py         # The massive script that produces 50,000 synthetic shipments mathematically engineered to teach the ML models what a delay looks like.
│   │   ├── hubs.py              # The Source of Truth. Contains the strict Python dictionary defining the exact 40 nationwide Hubs/Warehouses and their absolute GPS coordinates.
│   │   ├── network.py           # The mathematical compiler that forces total topological connectivity between the 40 hubs, generating 1,560 exact edges.
│   │   ├── traffic.py           # Real-world traffic simulator matrix.
│   │   ├── weather.py           # Historical/simulated weather generator used if the LIVE OpenWeather API is missing.
│   │   └── shipments.py         # Sub-module to simulate stochastic vehicle types and priority metrics randomly.
│   │
│   └── utils/                   # External API Clients
│       ├── osrm_api.py          # The live connection script to the Public Open Source Routing Machine for extracting real-world road geometries and distances.
│       ├── traffic_api.py       # TomTom traffic delay API connector.
│       └── weather_api.py       # OpenWeatherMap live connector.
│
├── configs/
│   └── config.yaml              # The Master Switchboard. Contains every single hyperparameter, weight function, threshold limit, and training split sizing rule for the whole repository.
│
├── data/                        # Datasets (Pre-Compiled and Safe)
│   ├── simulated/               # Where the raw 50,000 shipments are saved.
│   └── processed/               # Matrix-transformed mathematically ready data used by training.
│
├── .env                         # Your hidden API keys (e.g., OPENWEATHER_API_KEY).
├── requirements.txt             # Mandatory pip dependencies to run the system.
├── setup_and_run.py             # The aggressive one-shot automation script. It builds the 1560-edge network, simulates the 50,000 trips, trains XGBoost, selects the winner, and prepares the backend all in 1 command.
└── README.md                    # This file!
```

---

## 🚀 Quick Start Guide

### 1. Install System Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys (Highly Recommended but Optional)

Create or edit an `.env` file in the root with your keys to unlock real-time intelligence:

```env
OPENWEATHER_API_KEY=your_key_here     # Real-time weather overlays (optional)
TOMTOM_API_KEY=your_key_here          # Real-time traffic injection (optional)
```

> **Note:** The OSRM routing engine uses a completely free public API. No key is required for Map Geometry drawing. If TomTom/Weather keys are missing, the system gracefully mathematically simulates fallbacks instead.

### 3. Generate Mathematical Network & Train Intelligence

```bash
python setup_and_run.py
```

This single command:
1. Rebuilds the absolutely connected 40-node `hubs.py` and `network.csv` (1,560 edges).
2. Generates 50,000 synthetic historical shipments.
3. Bootstraps the pipeline, trains ML models (LR, RF, XGBoost), and drops the winning `.pkl` into the `/models/` folder.

### 4. Ignite the Fast Server

```bash
uvicorn src.api.main:app --port 8080 --reload
```

### 5. Access the Platform

- **Dashboard**: [http://localhost:8080](http://localhost:8080)
- **Automatic Docs Page**: [http://localhost:8080/docs](http://localhost:8080/docs)

---

## 🔌 API Reference Workflow (Backend Process)

When the user queries the dashboard, the following chain kicks off programmatically:

1. **`GET /hubs`**: Fired instantly on page load. Binds the 40 known Hubs and Warehouses straight to the frontend HTML `<select>` dropdown menus to prevent any typing errors (`422 Unprocessable Entity`).
2. **`POST /predict-route`**: Fired when the "Run Analysis" button is clicked. Sent straight to the Orchestrator with 1 Origin and up to 5 Destinations:
   - The **TSP Engine** generates sequential permutations.
   - The **NetworkX solver** fetches up to 5 intermediate detour paths per geographical step.
   - Internal synchronous calls fire to the **OSRM API** for distance lines/base duration, and to the **Weather/Traffic APIs**.
   - **XGBoost Classifier + Regressor** are engaged, predicting the precise Delay Probability and exact Delay Minutes.
   - The **Scorer** isolates the ultimate winning Permutation route via the 4-Factor cost equation and records the discarded unoptimized ones as "Alternatives," forcing everything dynamically back to `app.js` for Leaflet visualization!

---

**Created by Hardik Kumawat, Vardhan Bhati, Harshvardhan Sharma**
