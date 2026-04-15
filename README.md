<p align="center">
  <h1 align="center">🚚 Smart Logistics Intelligence (SLI)</h1>
  <p align="center">
    <strong>AI-Powered Supply Chain Delay Prediction & Multi-Stop Route Optimization Platform</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-Production-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/XGBoost-2.0+-FF6600?logo=xgboost&logoColor=white" alt="XGBoost">
    <img src="https://img.shields.io/badge/Google_Maps-Directions_API-4285F4?logo=googlemaps&logoColor=white" alt="Google Maps">
    <img src="https://img.shields.io/badge/Visual_Crossing-Weather_API-green" alt="Visual Crossing">
    <img src="https://img.shields.io/badge/Leaflet.js-Maps-199900?logo=leaflet&logoColor=white" alt="Leaflet">
  </p>
</p>

---

## 🎯 What Is This?

SLI is an end-to-end, production-ready logistics orchestrator that predicts **shipment delays** and calculates the **mathematically optimal multi-stop delivery route** across Indian hubs. It combines Machine Learning, external hardware-level Traffic/Weather sensing, and algorithmic Operations Research heuristics.

### Core Ecosystem:
- **Dual-Model ML Pipeline** — XGBoost Regressor and Classifiers trained on synthetic freight data to calculate precise risk probabilities.
- **Google Maps API Integration** — Complete road topology and base travel-time calculations.
- **External Environment APIs** — Live weather data (Visual Crossing) and real-time traffic jams (TomTom).
- **VRP Solver (The Multi-Hop Brain)** — Solves the Traveling Salesperson Problem (TSP) using a custom permutation heuristic.
- **4-Factor Route Scoring** — Scores route viability dynamically against: `Distance + Google ETA + Live Traffic + ML Weather Delay Risk`.
- **Modern Adaptive Dashboard** — Interactive Leaflet Map bindings, Light/Dark Modes, and a persistent SQLite Analytics Dashboard.

---

## 🖥️ Dashboard Features

The dashboard features a dynamic theme-switching glassmorphism design:
- **Light/Dark Toggle** — Flips CSS system variables dynamically (e.g., Carto Map instances swap from `dark_all` to `light_all` instantly).
- **Delay Probability Gauge** — Animated arcs showing ML risk percentage.
- **Dynamic Destination Injection** — Users can add and safely remove up to 6 unique multi-hop stops directly in the UI.
- **SHAP Feature Importance** — Explains the inner neural reasoning for the XGBoost output on why delays occur.
- **Persistent Analytics Hub** — Silent background HTTP fetches interface with SQLite to visualize Data Pipelines (Hourly trends, Riskiest Corridors) natively in browser charts.

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

### 2. Configure API Keys
Create a `.env` file in the project root containing your cloud provider keys:

```env
GOOGLE_MAPS_API_KEY=your_key_here     # For Base Duration and Polyline Polygons
VISUAL_CROSSING_API_KEY=your_key_here # For Live Weather querying
TOMTOM_API_KEY=your_key_here          # For Active Traffic Jams
```

### 3. Generate ML Models

```bash
python setup_and_run.py
```
This primes the ML weights by simulating 50,000 shipment routes through simulated traffic and storing the highest-accuracy XGBoost models inside the `/models` directory.

### 4. Start the Application

```bash
uvicorn src.api.main:app --port 8080 --reload --reload-dir src --reload-dir frontend
```

Navigate to **[http://localhost:8080](http://localhost:8080)** in your browser.

---

## ⚙️ Architecture & Workflow

### The "Run Analysis" Pipeline

```
          [User Submits Start & 4 Stops]
                        │
                        ▼
      FastAPI Orchestrator (/predict-route)
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │ 1. API Mapping Phase                  │
    │ - Google Maps: Queries geometric      │
    │   road lengths & base durations       │
    │ - Visual Crossing: Queries climate    │
    │ - TomTom: Checks for vehicle pileups  │
    └───────────────────┬───────────────────┘
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │ 2. Machine Learning Prediction Phase  │
    │ - Data feeds into XGBoost Model       │
    │ - Spits out `delay_probability` %     │
    └───────────────────┬───────────────────┘
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │ 3. VRP Heuristic Optimization Phase   │
    │ - Generates all permutation sequences │
    │ - Scores every leg via exactly:       │
    │   (Distance*x + Time*y + Traffic*z +  │
    │    Weather_Risk*w)                    │
    └───────────────────┬───────────────────┘
                        │
                        ▼
         [SQLite Auto-Save to Analytics]
                        │
                        ▼
       [Data Payload Sent Back to UI]
```

### The Operations Research Algorithm
When predicting multiple stops, normal **TSP (Traveling Salesperson Problem)** algorithms strictly solve for the shortest physical geometric line. 
This platform utilizes a **VRP (Vehicle Routing Problem)** engine scoring on a multi-dimensional array. A route spanning 400km with perfect weather might be heavily favored over a 380km route that passes directly through thunderstorms, drastically lowering fleet delivery lag.

---

## 📁 Source Code Topology

```
SLI/
├── frontend/                        # Web Dashboard (Vanilla HTML/CSS/JS)
│   ├── index.html                   # Contains Map Nodes and Analytics grids
│   ├── style.css                    # Design tokens and theme overrides
│   └── app.js                       # Logic Engine, Leaflet mapping, REST syncing
│
├── src/                             
│   ├── api/main.py                  # API router and Data orchestrator
│   ├── models/predict.py            # XGBoost Model inference loaders
│   ├── routing/optimizer.py         # Advanced VRP optimization execution
│   └── db/history.py                # Database wrapper for persistent tracking
│
├── configs/config.yaml              # Hyperparameters and strict thresholds
├── .env                             # (Hidden) Access Tokens
└── README.md
```

<p align="center">
  <sub>Engineered by <strong>Hardik Kumawat</strong> · <strong>Vardhan Bhati</strong> · <strong>Harshvardhan Sharma</strong></sub>
</p>
