"""
VitalLink AI — Anomaly Detection Module
=========================================
Detects rare / unseen physiological patterns using an LSTM Autoencoder.

How it works
------------
The LSTM Autoencoder is trained ONLY on "normal" vital sequences.
At inference time, abnormal sequences have a high reconstruction error
(MSE) because the encoder-decoder cannot faithfully reproduce patterns
it was never trained on.

A threshold (95th-percentile MSE on the validation normal set) separates
"normal" from "anomalous".

Architecture
------------
Encoder:
  LSTM(128, return_sequences=True)
  LSTM(64,  return_sequences=False)   → latent vector z
  RepeatVector(window_size)
Decoder:
  LSTM(64,  return_sequences=True)
  LSTM(128, return_sequences=True)
  TimeDistributed(Dense(n_features))  → reconstructed sequence
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Model builder
# ─────────────────────────────────────────────────────────────────────────
def build_lstm_autoencoder(
    window_size: int = 200,
    n_features: int = 5,
    latent_dim: int = 64,
) -> "tf.keras.Model":
    """
    Build and compile the LSTM Autoencoder.

    Args:
        window_size: Timesteps per input sequence.
        n_features:  Number of vital channels.
        latent_dim:  Bottleneck LSTM units.

    Returns:
        Compiled tf.keras.Model.
    """
    try:
        import tensorflow as tf
    except ImportError as e:
        raise ImportError("TensorFlow required. pip install tensorflow") from e

    inputs = tf.keras.Input(shape=(window_size, n_features), name="ae_input")

    # ── Encoder ──────────────────────────────────────────────────────────
    x = tf.keras.layers.LSTM(128, return_sequences=True,  name="enc_lstm1")(inputs)
    x = tf.keras.layers.LSTM(latent_dim, return_sequences=False, name="enc_lstm2")(x)

    # ── Bridge ────────────────────────────────────────────────────────────
    x = tf.keras.layers.RepeatVector(window_size, name="bridge")(x)

    # ── Decoder ───────────────────────────────────────────────────────────
    x = tf.keras.layers.LSTM(latent_dim, return_sequences=True, name="dec_lstm1")(x)
    x = tf.keras.layers.LSTM(128, return_sequences=True,  name="dec_lstm2")(x)
    outputs = tf.keras.layers.TimeDistributed(
        tf.keras.layers.Dense(n_features), name="reconstruction"
    )(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="VitalLink_LSTMAuto")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="mse",
        metrics=["mae"],
    )
    logger.info("LSTM Autoencoder built. Params: %d", model.count_params())
    return model


# ─────────────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────────────
def train_autoencoder(
    X_normal_train: np.ndarray,
    X_normal_val: np.ndarray,
    save_path: str = "models/anomaly_detector.h5",
    threshold_path: str = "models/anomaly_threshold.pkl",
    epochs: int = 80,
    batch_size: int = 32,
    threshold_percentile: float = 95.0,
) -> Tuple["tf.keras.Model", float]:
    """
    Train autoencoder on normal-only data and compute the anomaly threshold.

    Args:
        X_normal_train: Normal vital windows (N, T, F).
        X_normal_val:   Validation normal windows for threshold computation.
        save_path:      .h5 output path for the trained model.
        threshold_path: .pkl path to persist the computed MSE threshold.
        epochs:         Training epochs.
        batch_size:     Batch size.
        threshold_percentile: Percentile of val-MSE used as anomaly cutoff.

    Returns:
        (trained_model, mse_threshold)
    """
    import tensorflow as tf

    os.makedirs(Path(save_path).parent, exist_ok=True)

    model = build_lstm_autoencoder(
        window_size=X_normal_train.shape[1],
        n_features=X_normal_train.shape[2],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=8, restore_best_weights=True
        ),
        tf.keras.callbacks.ModelCheckpoint(
            save_path, monitor="val_loss", save_best_only=True
        ),
    ]

    model.fit(
        X_normal_train, X_normal_train,   # autoencoder: target = input
        validation_data=(X_normal_val, X_normal_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    # ── Compute threshold ────────────────────────────────────────────────
    reconstructed = model.predict(X_normal_val, verbose=0)
    mse_per_window = np.mean(
        np.square(X_normal_val - reconstructed), axis=(1, 2)
    )                                           # (N_val,)
    threshold = float(np.percentile(mse_per_window, threshold_percentile))

    with open(threshold_path, "wb") as f:
        pickle.dump({"threshold": threshold, "percentile": threshold_percentile}, f)

    logger.info(
        "Anomaly threshold (%.0f-pct MSE) = %.6f", threshold_percentile, threshold
    )
    return model, threshold


# ─────────────────────────────────────────────────────────────────────────
# Inference wrapper
# ─────────────────────────────────────────────────────────────────────────
class AnomalyDetector:
    """
    Stateless inference wrapper for Lambda deployment.

    Usage:
        detector = AnomalyDetector("models/anomaly_detector.h5",
                                    "models/anomaly_threshold.pkl")
        result = detector.detect(window_array)
    """

    _SEVERITY_MAP = [
        (2.0, "critical anomaly"),
        (1.0, "high anomaly"),
        (0.5, "moderate anomaly"),
        (0.0, "normal"),
    ]

    def __init__(self, model_path: str, threshold_path: str):
        import tensorflow as tf

        self._model = tf.keras.models.load_model(model_path, compile=False)
        with open(threshold_path, "rb") as f:
            meta = pickle.load(f)
        self._threshold: float = meta["threshold"]
        logger.info(
            "AnomalyDetector loaded. Threshold=%.6f", self._threshold
        )

    # ── public API ───────────────────────────────────────────────────────

    def detect(self, window: np.ndarray) -> Dict:
        """
        Args:
            window: np.ndarray shape (window_size, n_features) — normalized

        Returns:
            {
                "anomaly_score":       0.93,          # normalized 0–1
                "reconstruction_mse":  0.0412,
                "is_anomaly":          True,
                "status":              "critical anomaly detected",
                "severity":            "critical" | "high" | "moderate" | "normal",
            }
        """
        x = window[np.newaxis, ...]                        # (1, T, F)
        recon = self._model.predict(x, verbose=0)          # (1, T, F)
        mse = float(np.mean(np.square(window - recon[0])))

        is_anomaly = mse > self._threshold
        normalized_score = min(mse / (self._threshold * 2.0), 1.0)

        ratio = mse / (self._threshold + 1e-9)
        severity = "normal"
        for cutoff, label in self._SEVERITY_MAP:
            if ratio > cutoff:
                severity = label.split()[0]  # first word: critical/high/moderate/normal
                break

        return {
            "anomaly_score":      round(normalized_score, 4),
            "reconstruction_mse": round(mse, 6),
            "is_anomaly":         bool(is_anomaly),
            "status": (
                f"{severity} anomaly detected" if is_anomaly else "normal vital pattern"
            ),
            "severity": severity,
        }

    def batch_detect(self, windows: np.ndarray) -> np.ndarray:
        """
        Compute per-window MSE for an array of windows.

        Args:
            windows: (N, T, F)

        Returns:
            mse_scores: (N,)  float32
        """
        reconstructed = self._model.predict(windows, verbose=0)
        return np.mean(np.square(windows - reconstructed), axis=(1, 2))
