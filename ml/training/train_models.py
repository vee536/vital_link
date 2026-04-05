"""
VitalLink AI — Training Pipeline (v2 — Real Dataset)
======================================================
Trains all three models using healthcare_monitoring_dataset.csv.

What changed from v1
---------------------
  * Synthetic dataset generator replaced with real CSV loader
  * Blood Pressure parsed from "sys/dia" string format
  * Normalization constants updated to dataset-derived statistics
  * Class weights applied to CNN-LSTM to handle label imbalance
  * Autoencoder trained only on Normal-labelled windows
  * GRU labels derived from actual vital trends (not random)
  * Federated simulation uses dataset-derived windows (not noise)

What did NOT change
-------------------
  * Model architectures (CNN-LSTM, LSTM Autoencoder, GRU)
  * Saved model filenames (cnn_lstm_classifier.h5, etc.)
  * lambda_inference.py interface — fully compatible

Usage
-----
  # Train all models
  python training/train_models.py --mode all --csv data/healthcare_monitoring_dataset.csv

  # Train individual models
  python training/train_models.py --mode classifier
  python training/train_models.py --mode anomaly
  python training/train_models.py --mode gru
  python training/train_models.py --mode federated
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np

# ── path bootstrap ───────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.dataset_loader import (
    load_dataset,
    build_train_val_test_splits,
    get_normal_windows,
    compute_class_weights,
)
from preprocessing.preprocess_vitals import VitalsDatasetBuilder
from models.cnn_lstm_classifier import (
    train as train_classifier,
    evaluate as evaluate_classifier,
    CONDITION_LABELS,
)
from models.anomaly_detector import train_autoencoder
from models.gru_predictor import train as train_gru, generate_risk_labels
from federated_learning.fedavg import (
    FederatedClient,
    FedAvgAggregator,
    FederatedRunner,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("VitalLink.Training")

# ── output paths ─────────────────────────────────────────────────────────
MODEL_DIR = ROOT / "models" / "saved"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

PATHS = {
    "classifier": str(MODEL_DIR / "cnn_lstm_classifier.h5"),
    "anomaly":    str(MODEL_DIR / "anomaly_detector.h5"),
    "threshold":  str(MODEL_DIR / "anomaly_threshold.pkl"),
    "gru":        str(MODEL_DIR / "gru_predictor.h5"),
    "federated":  str(MODEL_DIR / "federated_global.h5"),
    "metrics":    str(MODEL_DIR / "training_metrics.json"),
}

# Default CSV path
DEFAULT_CSV = str(ROOT / "data" / "healthcare_monitoring_dataset.csv")


# ─────────────────────────────────────────────────────────────────────────
# Dataset loader wrapper
# ─────────────────────────────────────────────────────────────────────────
def _load_real_dataset(csv_path: str, window_size: int, stride: int):
    """
    Load the real CSV, build windows, and return train/val/test splits.

    Returns:
        X_train, y_train, X_val, y_val, X_test, y_test,
        normal_mask_train, normal_mask_val
    """
    logger.info("═══ Loading Real Dataset ═══")
    logger.info("CSV: %s", csv_path)

    df = load_dataset(csv_path)

    X_train, y_train, X_val, y_val, X_test, y_test = build_train_val_test_splits(
        df,
        window_size=window_size,
        stride=stride,
        val_ratio=0.15,
        test_ratio=0.15,
        random_seed=42,
    )

    # Boolean masks: True = Normal window (for autoencoder training)
    normal_mask_train = y_train[:, 0].astype(bool)
    normal_mask_val   = y_val[:, 0].astype(bool)

    logger.info(
        "Splits ready | train=%d  val=%d  test=%d",
        len(X_train), len(X_val), len(X_test),
    )
    logger.info(
        "Normal windows in train: %d (%.1f%%)",
        normal_mask_train.sum(), 100 * normal_mask_train.mean(),
    )
    return (
        X_train, y_train,
        X_val,   y_val,
        X_test,  y_test,
        normal_mask_train,
        normal_mask_val,
    )


# ─────────────────────────────────────────────────────────────────────────
# Training steps
# ─────────────────────────────────────────────────────────────────────────
def run_classifier_training(
    X_train, y_train, X_val, y_val, X_test, y_test,
) -> dict:
    logger.info("═══ Training CNN-LSTM Classifier ═══")

    # Compute class weights to handle imbalance (Hypoxia=3.9%, etc.)
    class_weights = compute_class_weights(y_train)

    model, history = train_classifier(
        X_train, y_train,
        X_val,   y_val,
        save_path=PATHS["classifier"],
        epochs=80,
        batch_size=32,
        class_weights=class_weights,
    )

    eval_metrics = evaluate_classifier(model, X_test, y_test)
    macro_auc = eval_metrics.get("roc_auc_macro", 0)
    logger.info("Classifier macro-AUC on test set: %.4f", macro_auc)

    # Log per-class results
    for label in CONDITION_LABELS:
        m = eval_metrics.get(label, {})
        logger.info(
            "  %-15s  precision=%.3f  recall=%.3f  f1=%.3f",
            label,
            m.get("precision", 0),
            m.get("recall", 0),
            m.get("f1-score", 0),
        )

    return {
        "history": {k: float(v[-1]) for k, v in history.items()},
        "eval": {
            k: v for k, v in eval_metrics.items()
            if k not in ("confusion_matrices",)  # keep metrics JSON-serializable
        },
    }


def run_anomaly_training(
    X_train, normal_mask_train, X_val, normal_mask_val,
) -> dict:
    logger.info("═══ Training LSTM Autoencoder Anomaly Detector ═══")

    X_normal_train = X_train[normal_mask_train]
    X_normal_val   = X_val[normal_mask_val]

    logger.info(
        "Autoencoder trains on Normal-only windows: train=%d  val=%d",
        len(X_normal_train), len(X_normal_val),
    )

    if len(X_normal_train) < 10:
        logger.warning(
            "Only %d normal windows — anomaly detector may underfit. "
            "Consider using stride > 1 to reduce window overlap.",
            len(X_normal_train),
        )

    _, threshold = train_autoencoder(
        X_normal_train, X_normal_val,
        save_path=PATHS["anomaly"],
        threshold_path=PATHS["threshold"],
        epochs=60,
        batch_size=32,
    )
    return {"anomaly_threshold": float(threshold)}


def run_gru_training(X_train, y_train, X_val, y_val) -> dict:
    logger.info("═══ Training GRU Deterioration Predictor ═══")

    # generate_risk_labels derives (icu_prob, mortality_risk, deterioration_prob)
    # from the actual vital time-series signals in the windows
    # Derive risk labels directly from CNN-LSTM classification labels
# deterioration = Hypoxia or Arrhythmia, icu = Cardiac Risk, mortality = Hypoxia
    y_risk_train = np.column_stack([
    y_train[:, 4],                                    # icu_probability = Cardiac Risk
    np.clip(y_train[:, 1] * 2, 0, 1),                # mortality_risk  = Hypoxia (amplified)
    np.clip(y_train[:, 1] + y_train[:, 2], 0, 1),    # deterioration   = Hypoxia + Arrhythmia
    ]).astype(np.float32)

    y_risk_val = np.column_stack([
    y_val[:, 4],
    np.clip(y_val[:, 1] * 2, 0, 1),
    np.clip(y_val[:, 1] + y_val[:, 2], 0, 1),
    ]).astype(np.float32)

    logger.info(
        "Risk label means — train: icu=%.3f mort=%.3f det=%.3f",
        y_risk_train[:, 0].mean(),
        y_risk_train[:, 1].mean(),
        y_risk_train[:, 2].mean(),
    )

    model, history = train_gru(
        X_train, y_risk_train,
        X_val,   y_risk_val,
        save_path=PATHS["gru"],
        epochs=60,
        batch_size=32,
    )
    return {"history": {k: float(v[-1]) for k, v in history.items()}}


def run_federated_training(
    X_train, y_train, X_val, y_val,
    window_size: int, n_features: int = 5,
) -> dict:
    """
    Simulate FedAvg across three hospital partitions using the real dataset.

    The dataset is partitioned into three equal non-overlapping segments
    (simulating Hospital A=first third, B=middle, C=last third).
    """
    logger.info("═══ Federated Learning Simulation (3 Hospitals) ═══")
    from models.cnn_lstm_classifier import build_cnn_lstm
    from federated_learning.fedavg import HospitalDataset

    # Partition real dataset chronologically across hospitals
    n = len(X_train)
    third = n // 3

    hospital_data = {
        "hospital_a": HospitalDataset(
            "hospital_a",
            X_train[:third],      y_train[:third],
            X_val[:len(X_val)//3], y_val[:len(X_val)//3],
        ),
        "hospital_b": HospitalDataset(
            "hospital_b",
            X_train[third:2*third],     y_train[third:2*third],
            X_val[len(X_val)//3:2*len(X_val)//3],
            y_val[len(X_val)//3:2*len(X_val)//3],
        ),
        "hospital_c": HospitalDataset(
            "hospital_c",
            X_train[2*third:], y_train[2*third:],
            X_val[2*len(X_val)//3:], y_val[2*len(X_val)//3:],
        ),
    }

    logger.info(
        "Hospital sizes: A=%d  B=%d  C=%d",
        hospital_data["hospital_a"].n_samples,
        hospital_data["hospital_b"].n_samples,
        hospital_data["hospital_c"].n_samples,
    )

    def model_builder():
        return build_cnn_lstm(window_size=window_size, n_features=n_features)

    global_model = model_builder()
    clients = [
        FederatedClient(
            hospital_id=h,
            dataset=hospital_data[h],
            model_builder_fn=model_builder,
            local_epochs=3,
            batch_size=32,
        )
        for h in ["hospital_a", "hospital_b", "hospital_c"]
    ]

    aggregator = FedAvgAggregator(global_model)
    runner = FederatedRunner(
        clients, aggregator,
        communication_rounds=10,
        save_path=PATHS["federated"],
    )
    fed_history = runner.run()
    final_auc = fed_history[-1]["mean_auc"]

    logger.info("Federated training complete | final mean AUC: %.4f", final_auc)
    return {"final_mean_auc": float(final_auc), "rounds": len(fed_history)}


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="VitalLink AI — Training Pipeline (real dataset)"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "classifier", "anomaly", "gru", "federated"],
        default="all",
        help="Which model(s) to train",
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help="Path to healthcare_monitoring_dataset.csv",
    )
    parser.add_argument(
        "--window",  type=int, default=200,
        help="Sliding window size in timesteps (default 200)",
    )
    parser.add_argument(
        "--stride", type=int, default=1,
        help="Window stride — smaller = more windows (default 1 → 9801 windows)",
    )
    args = parser.parse_args()

    all_metrics = {}

    # ── Load real dataset ─────────────────────────────────────────────────
    if args.mode in ("all", "classifier", "anomaly", "gru", "federated"):
        (
            X_train, y_train,
            X_val,   y_val,
            X_test,  y_test,
            normal_mask_train, normal_mask_val,
        ) = _load_real_dataset(args.csv, args.window, args.stride)

        logger.info(
            "Dataset loaded | train=%d  val=%d  test=%d  features=%d",
            len(X_train), len(X_val), len(X_test), X_train.shape[2],
        )

    if args.mode in ("all", "classifier"):
        all_metrics["classifier"] = run_classifier_training(
            X_train, y_train, X_val, y_val, X_test, y_test,
        )

    if args.mode in ("all", "anomaly"):
        all_metrics["anomaly"] = run_anomaly_training(
            X_train, normal_mask_train, X_val, normal_mask_val,
        )

    if args.mode in ("all", "gru"):
        all_metrics["gru"] = run_gru_training(X_train, y_train, X_val, y_val)

    if args.mode in ("all", "federated"):
        all_metrics["federated"] = run_federated_training(
            X_train, y_train, X_val, y_val,
            window_size=args.window,
        )

    # ── Save metrics report ───────────────────────────────────────────────
    with open(PATHS["metrics"], "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    logger.info("Training metrics saved → %s", PATHS["metrics"])
    logger.info("✅  Training complete. Models saved to: %s", MODEL_DIR)


if __name__ == "__main__":
    main()
