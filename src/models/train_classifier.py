"""
train_classifier.py  —  Multi-model training with automatic best model selection.

Trains three classifiers:
  1. Logistic Regression
  2. Random Forest
  3. XGBoost

Compares on ROC-AUC, PR-AUC, F1, accuracy.
Automatically selects the best model by ROC-AUC and saves it.

Run:
    python -m src.models.train_classifier
"""

import json
import joblib
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, recall_score, precision_score, accuracy_score,
    roc_auc_score, average_precision_score, classification_report,
)
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from src.features.build_training_features import FEATURE_COLUMNS, TARGET_COLUMN

CONFIG_PATH   = "configs/config.yaml"
FEATURES_PATH = "data/processed/train_features.csv"
MODEL_PATH    = "models/delay_classifier.pkl"
REPORTS_DIR   = Path("reports")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _tune_threshold(y_true, y_proba) -> tuple[float, float]:
    """Find threshold that maximises F1 on given data."""
    best_f1, best_t = 0.0, 0.5
    for t in np.arange(0.25, 0.75, 0.02):
        pred = (y_proba >= t).astype(int)
        f1 = f1_score(y_true, pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return best_t, best_f1


def _evaluate_model(y_true, y_proba, threshold):
    """Compute all metrics for a model."""
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "threshold":  round(float(threshold), 3),
        "accuracy":   round(float(accuracy_score(y_true, y_pred)), 4),
        "f1":         round(float(f1_score(y_true, y_pred)), 4),
        "recall":     round(float(recall_score(y_true, y_pred)), 4),
        "precision":  round(float(precision_score(y_true, y_pred)), 4),
        "roc_auc":    round(float(roc_auc_score(y_true, y_proba)), 4),
        "pr_auc":     round(float(average_precision_score(y_true, y_proba)), 4),
    }


def train(features_path: str = FEATURES_PATH, model_path: str = MODEL_PATH):

    cfg = load_config()["model"]
    xgb_cfg = cfg["xgboost"]
    lr_cfg  = cfg.get("logistic_regression", {})
    rf_cfg  = cfg.get("random_forest", {})

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading features...")
    df = pd.read_csv(features_path)
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].values
    print(f"  {len(df):,} rows | delay rate: {y.mean():.1%}")

    # ── Train / val / test split ──────────────────────────────────────────────
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size     = cfg["test_size"],
        stratify      = y,
        random_state  = 42,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size     = cfg["val_size"] / (1 - cfg["test_size"]),
        stratify      = y_temp,
        random_state  = 42,
    )
    print(f"  Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

    # ── Scale features (needed for Logistic Regression) ───────────────────────
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled   = scaler.transform(X_val)
    X_test_scaled  = scaler.transform(X_test)

    # ══════════════════════════════════════════════════════════════════════════
    # MODEL 1: LOGISTIC REGRESSION
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  Training Model 1/3: Logistic Regression")
    print("=" * 60)

    lr_model = LogisticRegression(
        C             = lr_cfg.get("C", 1.0),
        max_iter      = lr_cfg.get("max_iter", 1000),
        solver        = lr_cfg.get("solver", "lbfgs"),
        class_weight  = lr_cfg.get("class_weight", "balanced"),
        random_state  = 42,
        n_jobs        = -1,
    )
    lr_model.fit(X_train_scaled, y_train)

    lr_proba   = lr_model.predict_proba(X_test_scaled)[:, 1]
    lr_thresh, _ = _tune_threshold(y_val, lr_model.predict_proba(X_val_scaled)[:, 1])
    lr_metrics = _evaluate_model(y_test, lr_proba, lr_thresh)
    print(f"  ROC-AUC: {lr_metrics['roc_auc']:.4f} | F1: {lr_metrics['f1']:.4f} | Acc: {lr_metrics['accuracy']:.4f}")

    # ══════════════════════════════════════════════════════════════════════════
    # MODEL 2: RANDOM FOREST
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  Training Model 2/3: Random Forest")
    print("=" * 60)

    rf_model = RandomForestClassifier(
        n_estimators  = rf_cfg.get("n_estimators", 300),
        max_depth     = rf_cfg.get("max_depth", 12),
        min_samples_split = rf_cfg.get("min_samples_split", 5),
        min_samples_leaf  = rf_cfg.get("min_samples_leaf", 2),
        class_weight  = rf_cfg.get("class_weight", "balanced"),
        random_state  = 42,
        n_jobs        = -1,
    )
    rf_model.fit(X_train, y_train)

    rf_proba   = rf_model.predict_proba(X_test)[:, 1]
    rf_thresh, _ = _tune_threshold(y_val, rf_model.predict_proba(X_val)[:, 1])
    rf_metrics = _evaluate_model(y_test, rf_proba, rf_thresh)
    print(f"  ROC-AUC: {rf_metrics['roc_auc']:.4f} | F1: {rf_metrics['f1']:.4f} | Acc: {rf_metrics['accuracy']:.4f}")

    # ══════════════════════════════════════════════════════════════════════════
    # MODEL 3: XGBOOST
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  Training Model 3/3: XGBoost")
    print("=" * 60)

    xgb_model = XGBClassifier(
        n_estimators         = xgb_cfg["n_estimators"],
        max_depth            = xgb_cfg["max_depth"],
        learning_rate        = xgb_cfg["learning_rate"],
        subsample            = xgb_cfg["subsample"],
        colsample_bytree     = xgb_cfg["colsample_bytree"],
        min_child_weight     = xgb_cfg["min_child_weight"],
        gamma                = xgb_cfg["gamma"],
        reg_alpha            = xgb_cfg["reg_alpha"],
        reg_lambda           = xgb_cfg["reg_lambda"],
        scale_pos_weight     = xgb_cfg["scale_pos_weight"],
        eval_metric          = xgb_cfg["eval_metric"],
        early_stopping_rounds= xgb_cfg["early_stopping_rounds"],
        random_state         = 42,
        n_jobs               = -1,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set = [(X_val, y_val)],
        verbose  = 50,
    )

    xgb_proba  = xgb_model.predict_proba(X_test)[:, 1]
    xgb_thresh, _ = _tune_threshold(y_val, xgb_model.predict_proba(X_val)[:, 1])
    xgb_metrics = _evaluate_model(y_test, xgb_proba, xgb_thresh)
    print(f"  ROC-AUC: {xgb_metrics['roc_auc']:.4f} | F1: {xgb_metrics['f1']:.4f} | Acc: {xgb_metrics['accuracy']:.4f}")

    # ══════════════════════════════════════════════════════════════════════════
    # COMPARE & SELECT BEST MODEL
    # ══════════════════════════════════════════════════════════════════════════
    comparison = {
        "logistic_regression": lr_metrics,
        "random_forest":       rf_metrics,
        "xgboost":             xgb_metrics,
    }

    print("\n" + "=" * 60)
    print("  MODEL COMPARISON — Test Set Results")
    print("=" * 60)
    print(f"  {'Model':<25} {'ROC-AUC':>9} {'PR-AUC':>9} {'F1':>9} {'Accuracy':>9} {'Threshold':>10}")
    print("  " + "-" * 75)
    for name, m in comparison.items():
        print(f"  {name:<25} {m['roc_auc']:>9.4f} {m['pr_auc']:>9.4f} {m['f1']:>9.4f} {m['accuracy']:>9.4f} {m['threshold']:>10.3f}")

    # Select by ROC-AUC (best overall discrimination)
    best_name = max(comparison, key=lambda k: comparison[k]["roc_auc"])
    print(f"\n  🏆 Best model: {best_name} (ROC-AUC = {comparison[best_name]['roc_auc']:.4f})")

    # Map to actual model objects
    model_map = {
        "logistic_regression": (lr_model, lr_thresh, True),   # needs_scaling=True
        "random_forest":       (rf_model, rf_thresh, False),
        "xgboost":             (xgb_model, xgb_thresh, False),
    }

    best_model, best_thresh, needs_scaling = model_map[best_name]

    # ── Print classification report for best model ────────────────────────────
    if needs_scaling:
        best_proba = best_model.predict_proba(X_test_scaled)[:, 1]
    else:
        best_proba = best_model.predict_proba(X_test)[:, 1]
    best_pred = (best_proba >= best_thresh).astype(int)

    print(f"\n── {best_name} — Detailed Classification Report ──")
    print(classification_report(y_test, best_pred, target_names=["On-time", "Delayed"]))

    # ── Save model bundle ────────────────────────────────────────────────────
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model":           best_model,
        "model_name":      best_name,
        "feature_columns": FEATURE_COLUMNS,
        "threshold":       best_thresh,
        "needs_scaling":   needs_scaling,
        "scaler":          scaler if needs_scaling else None,
        "comparison":      comparison,
    }
    joblib.dump(bundle, model_path)
    print(f"\nModel saved → {model_path}")

    # ── Save comparison report ───────────────────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "best_model":  best_name,
        "selection_criterion": "roc_auc",
        "models": comparison,
    }
    with open(REPORTS_DIR / "model_comparison.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Comparison saved → reports/model_comparison.json")

    return best_model, best_thresh


if __name__ == "__main__":
    train()
