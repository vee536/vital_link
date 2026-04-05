"""
VitalLink AI — Utilities
=========================
Shared helpers used across training, evaluation, and deployment.

Modules
-------
  metrics      — per-condition AUC/F1 reporting
  visualization — confusion matrix, ROC curves, training curves
  export        — TFLite conversion, ONNX export, model size report
  data_io       — S3 loader, local CSV loader
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Metrics helpers
# ─────────────────────────────────────────────────────────────────────────
def print_classification_report(metrics: Dict, condition_labels: List[str]) -> None:
    """Pretty-print per-class metrics from the evaluate() output dict."""
    print("\n" + "═" * 60)
    print("  VitalLink — Classification Report")
    print("═" * 60)
    print(f"  {'Condition':<20} {'Precision':>10} {'Recall':>8} {'F1':>8} {'AUC':>8}")
    print("─" * 60)

    auc_map = metrics.get("roc_auc_per_class", {})
    for label in condition_labels:
        label_metrics = metrics.get(label, {})
        print(
            f"  {label:<20}"
            f"  {label_metrics.get('precision', 0):>8.3f}"
            f"  {label_metrics.get('recall', 0):>6.3f}"
            f"  {label_metrics.get('f1-score', 0):>6.3f}"
            f"  {auc_map.get(label, 0):>6.3f}"
        )
    print("─" * 60)
    print(f"  {'Macro AUC':<20}  {'':>8}  {'':>6}  {'':>6}  {metrics.get('roc_auc_macro', 0):>6.3f}")
    print("═" * 60 + "\n")


def compute_optimal_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    condition_labels: List[str],
) -> Dict[str, float]:
    """
    Compute per-class thresholds that maximise F1 score.
    Useful for imbalanced healthcare datasets.
    """
    from sklearn.metrics import f1_score

    thresholds = {}
    for i, label in enumerate(condition_labels):
        best_t, best_f1 = 0.5, 0.0
        for t in np.linspace(0.1, 0.9, 81):
            y_pred_t = (y_prob[:, i] >= t).astype(int)
            f1 = f1_score(y_true[:, i], y_pred_t, zero_division=0)
            if f1 > best_f1:
                best_f1, best_t = f1, t
        thresholds[label] = round(float(best_t), 3)
        logger.info("[%s] optimal threshold=%.3f  F1=%.4f", label, best_t, best_f1)
    return thresholds


# ─────────────────────────────────────────────────────────────────────────
# Visualization
# ─────────────────────────────────────────────────────────────────────────
def plot_training_curves(history: Dict, save_dir: str = "outputs") -> None:
    """Plot loss, AUC, and accuracy curves from a Keras history dict."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping plots")
        return

    os.makedirs(save_dir, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("VitalLink — Training Curves", fontsize=14)

    for ax, (metric, title) in zip(
        axes,
        [("loss", "Loss"), ("auc", "AUC"), ("accuracy", "Accuracy")],
    ):
        if metric in history:
            ax.plot(history[metric], label="train")
        if f"val_{metric}" in history:
            ax.plot(history[f"val_{metric}"], label="val")
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.legend()
        ax.grid(True, alpha=0.3)

    path = Path(save_dir) / "training_curves.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    logger.info("Training curves saved → %s", path)
    plt.close(fig)


def plot_confusion_matrices(
    cm_dict: Dict[str, List],
    save_dir: str = "outputs",
) -> None:
    """Render per-class confusion matrices as a multi-panel figure."""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib / seaborn not installed — skipping CM plots")
        return

    n = len(cm_dict)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 4 * rows))
    axes = np.array(axes).flatten()

    for ax, (label, cm) in zip(axes, cm_dict.items()):
        cm_arr = np.array(cm)
        sns.heatmap(cm_arr, annot=True, fmt="d", ax=ax,
                    cmap="Blues", xticklabels=["Pred 0", "Pred 1"],
                    yticklabels=["True 0", "True 1"])
        ax.set_title(label)

    for ax in axes[n:]:
        ax.set_visible(False)

    path = Path(save_dir) / "confusion_matrices.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    logger.info("Confusion matrices saved → %s", path)
    plt.close(fig)


def plot_roc_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    condition_labels: List[str],
    save_dir: str = "outputs",
) -> None:
    """Multi-class ROC curves on one figure."""
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import roc_curve, auc
    except ImportError:
        logger.warning("sklearn / matplotlib required for ROC curves")
        return

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = plt.cm.tab10(np.linspace(0, 1, len(condition_labels)))

    for i, (label, color) in enumerate(zip(condition_labels, colors)):
        try:
            fpr, tpr, _ = roc_curve(y_true[:, i], y_prob[:, i])
            roc_auc = auc(fpr, tpr)
            ax.plot(fpr, tpr, color=color, lw=2,
                    label=f"{label} (AUC = {roc_auc:.3f})")
        except ValueError:
            pass

    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("VitalLink — Multi-Label ROC Curves")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)

    path = Path(save_dir) / "roc_curves.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    logger.info("ROC curves saved → %s", path)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────
# Model export helpers
# ─────────────────────────────────────────────────────────────────────────
def export_tflite(
    keras_model_path: str,
    output_path: str,
    quantize: bool = True,
) -> str:
    """
    Convert a saved Keras .h5 model to TFLite format.
    Quantization reduces size by ~4x and improves Lambda cold-start.

    Args:
        keras_model_path: Path to .h5 model file.
        output_path:      Destination .tflite path.
        quantize:         Apply INT8 dynamic quantization if True.

    Returns:
        Path to the output .tflite file.
    """
    import tensorflow as tf

    model = tf.keras.models.load_model(keras_model_path, compile=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    if quantize:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

    tflite_model = converter.convert()
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(tflite_model)

    original_mb = os.path.getsize(keras_model_path) / 1e6
    tflite_mb   = os.path.getsize(output_path)      / 1e6
    logger.info(
        "TFLite export: %.1f MB → %.1f MB (%.0f%% reduction)",
        original_mb, tflite_mb, 100 * (1 - tflite_mb / original_mb),
    )
    return output_path


def model_size_report(model_dir: str) -> Dict[str, str]:
    """Return a dict of filename → human-readable size for all models."""
    report = {}
    for path in Path(model_dir).glob("**/*"):
        if path.is_file() and path.suffix in (".h5", ".pkl", ".tflite"):
            mb = path.stat().st_size / 1e6
            report[path.name] = f"{mb:.2f} MB"
    return report


# ─────────────────────────────────────────────────────────────────────────
# Data I/O
# ─────────────────────────────────────────────────────────────────────────
def load_records_from_csv(csv_path: str) -> list:
    """
    Load a flat CSV of vital readings into a list of dicts.

    Expected CSV columns: timestamp, heart_rate, spo2, bp_sys, bp_dia, temperature
    Optional columns:     patient_id, label_*
    """
    import csv

    records = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "timestamp": row.get("timestamp"),
                "vitals": {
                    k: float(row[k])
                    for k in ("heart_rate", "spo2", "bp_sys", "bp_dia", "temperature")
                    if k in row and row[k]
                },
            }
            # Preserve any label columns
            for key in row:
                if key.startswith("label_"):
                    record[key] = row[key]
            records.append(record)
    logger.info("Loaded %d records from %s", len(records), csv_path)
    return records


def load_records_from_s3(bucket: str, key: str) -> list:
    """
    Download a JSON-lines vital records file from S3.

    Requires boto3 and appropriate IAM permissions.
    """
    import boto3, io

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    lines = obj["Body"].read().decode("utf-8").strip().split("\n")
    records = [json.loads(line) for line in lines if line.strip()]
    logger.info("Loaded %d records from s3://%s/%s", len(records), bucket, key)
    return records
