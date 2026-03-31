#!/usr/bin/env python3
"""
setup_and_run.py  —  One-shot end-to-end pipeline runner.

Run from the project root:
    python setup_and_run.py

Steps:
    1. Generate 50,000 synthetic shipments
    2. Build training features
    3. Train & compare 3 ML models (LR, RF, XGBoost) — auto-select best
    4. Evaluate and print metrics
    5. Generate hubs.csv and network.csv for the routing engine
    6. Print instructions to start API and dashboard
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))


def step(n: int, desc: str):
    print(f"\n{'='*60}")
    print(f"  Step {n}: {desc}")
    print(f"{'='*60}")


def main():
    t0 = time.time()

    # ── Step 1: Generate data ─────────────────────────────────────────────────
    step(1, "Generating synthetic shipment dataset (50,000 rows)...")
    from src.simulator.generator import save_dataset
    save_dataset()

    # ── Step 2: Build hubs.csv and network.csv ────────────────────────────────
    step(2, "Saving hub and network files...")
    from src.simulator.hubs import save_hubs_csv
    from src.simulator.network import save_network_csv
    save_hubs_csv("data/hubs.csv")
    save_network_csv("data/network.csv")

    # ── Step 3: Build training features ──────────────────────────────────────
    step(3, "Building training feature matrix...")
    from src.features.build_training_features import run as build_features
    build_features()

    # ── Step 4: Train & compare models ────────────────────────────────────────
    step(4, "Training 3 models (LR, RF, XGBoost) and selecting best...")
    from src.models.train_classifier import train
    train()

    # ── Step 5: Evaluate ──────────────────────────────────────────────────────
    step(5, "Evaluating best model on test set...")
    from src.models.evaluate import evaluate
    evaluate()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Setup complete in {elapsed:.0f}s")
    print(f"{'='*60}")
    print("""
Next steps:

  Start the API:
    uvicorn src.api.main:app --reload --port 8000

  Start the dashboard (in a new terminal):
    streamlit run app/streamlit_app.py

  API docs:
    http://localhost:8000/docs

  Health check:
    http://localhost:8000/health
""")


if __name__ == "__main__":
    main()
