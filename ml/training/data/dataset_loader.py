"""
VitalLink AI — Dataset Loader
================================
Loads and prepares healthcare_monitoring_dataset.csv for training.

Dataset facts (from analysis)
------------------------------
  Rows          : 10,000
  Interval      : 10 minutes per reading
  Duration      : ~69 days (2023-06-04 → 2023-08-12)
  Source type   : Single continuous patient time-series
  Missing values: None

Columns used (5 features)
--------------------------
  Heart Rate (bpm)              → heart_rate
  Blood Oxygen Level (SpO2 %)   → spo2
  Blood Pressure (mmHg)         → split → bp_sys / bp_dia
  Body Temperature (°C)         → temperature

Columns intentionally dropped
------------------------------
  Glucose Level (mg/dL)              — excluded per project requirements
  Respiratory Rate (breaths/min)     — excluded to preserve (200, 5) inference shape

Window-level label thresholds (calibrated to dataset distribution)
-------------------------------------------------------------------
  Hypoxia      >20% of window readings with SpO2 < 97%
  Arrhythmia   HR std > 10.5 bpm within window
  Fever        any reading > 38.0 °C
  Cardiac Risk max SysBP > 160 mmHg OR >5% readings with HR < 50 bpm
  Normal       none of the above
  Shock        not present in this dataset (always 0)

Resulting label prevalence (stride=1, 9,801 windows)
------------------------------------------------------
  Normal: 32.3% | Hypoxia: 3.9% | Arrhythmia: 15.9%
  Fever: 25.0%  | Cardiac Risk: 52.4% | Shock: 0%
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Default path — override via env var or argument
DEFAULT_CSV = os.environ.get(
    "VITALLINK_DATASET",
    str(Path(__file__).resolve().parent.parent / "data" / "healthcare_monitoring_dataset.csv"),
)


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

def load_dataset(csv_path: str = DEFAULT_CSV):
    """
    Load the raw CSV into a cleaned pandas DataFrame.

    Steps:
      1. Read CSV
      2. Parse Timestamp → datetime
      3. Split 'Blood Pressure (mmHg)' → bp_sys / bp_dia (int columns)
      4. Drop Glucose and Respiratory Rate columns
      5. Drop any duplicate timestamps
      6. Sort chronologically

    Returns:
        Cleaned pandas DataFrame ready for VitalsDatasetBuilder.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("pandas required: pip install pandas") from e

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at: {csv_path}\n"
            f"Set VITALLINK_DATASET env var or pass csv_path explicitly."
        )

    logger.info("Loading dataset from: %s", csv_path)
    df = pd.read_csv(csv_path)

    # ── Parse timestamp ───────────────────────────────────────────────────
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.drop_duplicates(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

    # ── Parse blood pressure string "sys/dia" → two int columns ──────────
    df = parse_blood_pressure(df)

    # ── Drop excluded columns ─────────────────────────────────────────────
    columns_to_drop = ["Glucose Level (mg/dL)", "Respiratory Rate (breaths/min)"]
    existing_drops = [c for c in columns_to_drop if c in df.columns]
    df = df.drop(columns=existing_drops)
    logger.info("Dropped columns: %s", existing_drops)

    # ── Validate required columns ─────────────────────────────────────────
    required = [
        "Timestamp",
        "Heart Rate (bpm)",
        "Blood Oxygen Level (SpO2 %)",
        "Body Temperature (°C)",
        "bp_sys",
        "bp_dia",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after parsing: {missing}")

    logger.info(
        "Dataset loaded: %d rows | %s → %s | interval=%s",
        len(df),
        df["Timestamp"].min(),
        df["Timestamp"].max(),
        _infer_interval(df),
    )
    _log_stats(df)
    return df


def parse_blood_pressure(df) -> object:
    """
    Split 'Blood Pressure (mmHg)' column from 'sys/dia' string
    into integer columns bp_sys and bp_dia.

    Example: '109/83' → bp_sys=109, bp_dia=83
    """
    bp_split = df["Blood Pressure (mmHg)"].str.split("/", expand=True)
    df = df.copy()
    df["bp_sys"] = bp_split[0].astype(int)
    df["bp_dia"] = bp_split[1].astype(int)
    df = df.drop(columns=["Blood Pressure (mmHg)"])
    return df


def build_train_val_test_splits(
    df,
    window_size: int = 200,
    stride: int = 1,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build normalized sliding-window tensors and split into train/val/test.

    Since this is a single continuous time series, windows are first built
    (preserving temporal order), then SHUFFLED before splitting to prevent
    adjacent windows from appearing in both train and val sets.

    Args:
        df:          Cleaned DataFrame from load_dataset().
        window_size: Timesteps per window (default 200).
        stride:      Stride between windows (default 1 → 9,801 windows).
        val_ratio:   Fraction of windows for validation.
        test_ratio:  Fraction of windows for test.
        random_seed: NumPy random seed for reproducible splits.

    Returns:
        X_train, y_train, X_val, y_val, X_test, y_test
        All shape (N, window_size, 5) for X and (N, 6) for y.
    """
    from preprocessing.preprocess_vitals import VitalsDatasetBuilder

    builder = VitalsDatasetBuilder(window_size=window_size, stride=stride)
    X, y = builder.build_from_dataframe(df)

    # Shuffle (important: temporal proximity between adjacent windows would leak)
    rng = np.random.default_rng(random_seed)
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]

    n = len(X)
    n_test = int(n * test_ratio)
    n_val  = int(n * val_ratio)
    n_train = n - n_val - n_test

    X_train = X[:n_train];          y_train = y[:n_train]
    X_val   = X[n_train:n_train+n_val]; y_val = y[n_train:n_train+n_val]
    X_test  = X[n_train+n_val:];    y_test  = y[n_train+n_val:]

    logger.info(
        "Splits: train=%d  val=%d  test=%d  (window_size=%d, stride=%d)",
        len(X_train), len(X_val), len(X_test), window_size, stride,
    )
    return X_train, y_train, X_val, y_val, X_test, y_test


def get_normal_windows(
    X: np.ndarray,
    y: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return only windows labelled as Normal (y[:,0] == 1).
    Used to train the LSTM Autoencoder anomaly detector on clean data only.
    """
    mask = y[:, 0].astype(bool)
    logger.info("Normal windows: %d / %d (%.1f%%)", mask.sum(), len(y), 100*mask.mean())
    return X[mask], y[mask]


def compute_class_weights(y: np.ndarray) -> Dict[int, float]:
    """
    Compute per-class weights to handle label imbalance.

    Formula: weight_k = total_samples / (n_classes * count_k)
    Classes with zero samples receive weight=1.0.
    """
    n_samples, n_classes = y.shape
    weights = {}
    for k in range(n_classes):
        count = y[:, k].sum()
        if count > 0:
            weights[k] = float(n_samples / (n_classes * count))
        else:
            weights[k] = 1.0
    logger.info("Class weights: %s", {k: f"{v:.2f}" for k, v in weights.items()})
    return weights


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _infer_interval(df) -> str:
    if len(df) > 1:
        delta = df["Timestamp"].iloc[1] - df["Timestamp"].iloc[0]
        total_minutes = int(delta.total_seconds() / 60)
        return f"{total_minutes} min"
    return "unknown"


def _log_stats(df) -> None:
    """Log a quick stats summary to confirm the load was correct."""
    cols = ["Heart Rate (bpm)", "Blood Oxygen Level (SpO2 %)",
            "Body Temperature (°C)", "bp_sys", "bp_dia"]
    for col in cols:
        if col in df.columns:
            s = df[col]
            logger.info(
                "  %-35s mean=%.2f  std=%.2f  min=%.1f  max=%.1f",
                col, s.mean(), s.std(), s.min(), s.max(),
            )


# ─────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    df = load_dataset(csv_path)

    X_tr, y_tr, X_v, y_v, X_te, y_te = build_train_val_test_splits(
        df, window_size=200, stride=10
    )
    print(f"\nX_train: {X_tr.shape}  y_train: {y_tr.shape}")
    print(f"X_val:   {X_v.shape}   y_val:   {y_v.shape}")
    print(f"X_test:  {X_te.shape}  y_test:  {y_te.shape}")

    X_norm, _ = get_normal_windows(X_tr, y_tr)
    print(f"Normal-only (for autoencoder): {X_norm.shape}")
