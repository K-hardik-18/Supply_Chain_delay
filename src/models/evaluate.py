"""
evaluate.py  —  Evaluate the saved model on the held-out test set.

Produces:
  - Console report with all metrics
  - reports/evaluation_report.json
  - reports/confusion_matrix.png
  - reports/shap_summary.png

Run:
    python -m src.models.evaluate
"""

import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, recall_score, precision_score, accuracy_score,
    roc_auc_score, average_precision_score,
    confusion_matrix, ConfusionMatrixDisplay,
)
import shap

from src.features.build_training_features import FEATURE_COLUMNS, TARGET_COLUMN

MODEL_PATH    = "models/delay_classifier.pkl"
FEATURES_PATH = "data/processed/train_features.csv"
REPORTS_DIR   = Path("reports")


def evaluate():
    REPORTS_DIR.mkdir(exist_ok=True)

    # ── Load model + data ─────────────────────────────────────────────────────
    bundle     = joblib.load(MODEL_PATH)
    model      = bundle["model"]
    threshold  = bundle.get("threshold", 0.42)
    model_name = bundle.get("model_name", "xgboost")
    needs_scaling = bundle.get("needs_scaling", False)
    scaler     = bundle.get("scaler", None)
    comparison = bundle.get("comparison", {})

    print(f"\n  Selected model: {model_name}")

    df = pd.read_csv(FEATURES_PATH)
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].values

    # Reproduce same test split as training
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.15, stratify=y, random_state=42)

    # Apply scaling if needed
    X_test_input = X_test
    if needs_scaling and scaler is not None:
        X_test_input = scaler.transform(X_test)

    # ── Metrics ───────────────────────────────────────────────────────────────
    y_proba = model.predict_proba(X_test_input)[:, 1]
    y_pred  = (y_proba >= threshold).astype(int)

    metrics = {
        "model_name":     model_name,
        "n_test":         len(y_test),
        "delay_rate":     float(y_test.mean()),
        "threshold":      float(threshold),
        "accuracy":       round(float(accuracy_score(y_test, y_pred)), 4),
        "roc_auc":        round(float(roc_auc_score(y_test, y_proba)), 4),
        "pr_auc":         round(float(average_precision_score(y_test, y_proba)), 4),
        "f1":             round(float(f1_score(y_test, y_pred)), 4),
        "recall":         round(float(recall_score(y_test, y_pred)), 4),
        "precision":      round(float(precision_score(y_test, y_pred)), 4),
    }

    print("\n── Evaluation Report ──────────────────────────")
    for k, v in metrics.items():
        print(f"  {k:<18}: {v}")

    # ── Print multi-model comparison if available ─────────────────────────────
    if comparison:
        print("\n── Multi-Model Comparison ─────────────────────")
        print(f"  {'Model':<25} {'ROC-AUC':>9} {'F1':>9} {'Accuracy':>9}")
        print("  " + "-" * 55)
        for name, m in comparison.items():
            marker = " 🏆" if name == model_name else ""
            print(f"  {name:<25} {m['roc_auc']:>9.4f} {m['f1']:>9.4f} {m['accuracy']:>9.4f}{marker}")

    with open(REPORTS_DIR / "evaluation_report.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # ── Confusion matrix ─────────────────────────────────────────────────────
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay(cm, display_labels=["On-time", "Delayed"]).plot(ax=ax, cmap="Blues")
    ax.set_title(f"Confusion Matrix — {model_name} (Test Set)")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=150)
    plt.close(fig)
    print(f"\nSaved → reports/confusion_matrix.png")

    # ── SHAP summary ──────────────────────────────────────────────────────────
    try:
        if model_name in ("xgboost", "random_forest"):
            explainer = shap.TreeExplainer(model)
            sample = X_test[:500]
        else:
            explainer = shap.LinearExplainer(model, masker=None)
            sample = X_test_input[:500]

        shap_values = explainer.shap_values(sample)

        fig = plt.figure(figsize=(8, 6))
        shap.summary_plot(
            shap_values, sample,
            feature_names=FEATURE_COLUMNS,
            show=False,
            plot_type="bar",
        )
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("Saved → reports/shap_summary.png")
    except Exception as e:
        print(f"SHAP summary plot skipped: {e}")


if __name__ == "__main__":
    evaluate()
