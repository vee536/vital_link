"""
VitalLink AI — GRU Deterioration Predictor
============================================
Predicts patient deterioration within the next 10–30 minutes.

Architecture
------------
Input  (batch, window_size, n_features)
  → GRU(128, return_sequences=True)
  → Dropout(0.3)
  → GRU(64, return_sequences=True)
  → Dropout(0.3)
  → GRU(32, return_sequences=False)
  → Dense(64, relu)
  → Dropout(0.3)
  → Dense(3, sigmoid)   ← [icu_prob, mortality_risk, deterioration_prob]

Outputs (all in [0, 1])
-----------------------
icu_probability      — probability patient will require ICU admission
mortality_risk       — risk of adverse outcome in next 10–30 min
deterioration_prob   — probability of measurable clinical deterioration

Training target construction
-----------------------------
Labels are derived from future vital windows:
  - deterioration_prob: SpO2 drops > 5%, HR spikes > 30 bpm, etc.
  - icu_probability:    clinical outcome annotation
  - mortality_risk:     in-hospital mortality label (binary)

The model is trained with a combined MSE + BCE loss on the three heads.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

RISK_LABELS: list = ["icu_probability", "mortality_risk", "deterioration_prob"]


# ─────────────────────────────────────────────────────────────────────────
# Model builder
# ─────────────────────────────────────────────────────────────────────────
def build_gru_predictor(
    window_size: int = 200,
    n_features: int = 5,
    gru_units: Tuple[int, int, int] = (128, 64, 32),
    dropout_rate: float = 0.3,
) -> "tf.keras.Model":
    """
    Construct and compile the GRU-based risk predictor.

    Args:
        window_size:  Input timesteps.
        n_features:   Vital channels.
        gru_units:    Units for each of the three GRU layers.
        dropout_rate: Dropout fraction.

    Returns:
        Compiled tf.keras.Model.
    """
    try:
        import tensorflow as tf
    except ImportError as e:
        raise ImportError("TensorFlow required. pip install tensorflow") from e

    inputs = tf.keras.Input(shape=(window_size, n_features), name="vitals_input")

    x = tf.keras.layers.GRU(gru_units[0], return_sequences=True, name="gru1")(inputs)
    x = tf.keras.layers.Dropout(dropout_rate, name="drop1")(x)

    x = tf.keras.layers.GRU(gru_units[1], return_sequences=True, name="gru2")(x)
    x = tf.keras.layers.Dropout(dropout_rate, name="drop2")(x)

    x = tf.keras.layers.GRU(gru_units[2], return_sequences=False, name="gru3")(x)

    x = tf.keras.layers.Dense(64, activation="relu", name="dense1")(x)
    x = tf.keras.layers.Dropout(dropout_rate, name="drop3")(x)

    # Three sigmoid outputs — each predicts a separate risk dimension
    outputs = tf.keras.layers.Dense(
        len(RISK_LABELS), activation="sigmoid", name="risk_output"
    )(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="VitalLink_GRU")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.AUC(name="auc", multi_label=True),
            tf.keras.metrics.MeanAbsoluteError(name="mae"),
        ],
    )
    logger.info("GRU Predictor built. Params: %d", model.count_params())
    return model


# ─────────────────────────────────────────────────────────────────────────
# Label auto-generation from vital signals (heuristic, for demo training)
# ─────────────────────────────────────────────────────────────────────────
def generate_risk_labels(
    windows: np.ndarray,
    future_windows: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Heuristically derive (icu_prob, mortality_risk, deterioration_prob) labels
    from the vital data itself.  In production, use clinician-annotated labels.

    Heuristics (on raw / de-normalised scale):
      deterioration: significant drop in SpO2 OR spike in HR
      icu_prob:       severe combined distress score
      mortality_risk: extreme combined outlier score

    Args:
        windows:        (N, T, F) normalized windows
        future_windows: (N, T, F) optional look-ahead windows

    Returns:
        labels: (N, 3) float32 in [0, 1]
    """
    N = len(windows)
    labels = np.zeros((N, 3), dtype=np.float32)

    # De-normalise SpO2 (idx=1) and HR (idx=0) for interpretable thresholds
    MEAN_HR, STD_HR = 69.47, 10.03
    MEAN_SPO2, STD_SPO2 = 97.51, 1.05

    # Per-window statistics
    mean_hr   = windows[:, :, 0].mean(axis=1) * STD_HR   + MEAN_HR
    mean_spo2 = windows[:, :, 1].mean(axis=1) * STD_SPO2 + MEAN_SPO2
    mean_bpsys = windows[:, :, 2].mean(axis=1) * 20.0    + 120.0

    # ── Deterioration ─────────────────────────────────────────────────
    spo2_score = np.clip((97.0 - mean_spo2) / 15.0, 0, 1)  # drops below 97
    hr_score   = np.clip((mean_hr - 100.0) / 60.0, 0, 1)   # tachycardia
    labels[:, 2] = np.clip(0.5 * spo2_score + 0.5 * hr_score, 0, 1)

    # ── ICU probability ───────────────────────────────────────────────
    bp_score  = np.clip((mean_bpsys - 140.0) / 60.0, 0, 1)
    icu_score = np.clip(0.4 * spo2_score + 0.3 * hr_score + 0.3 * bp_score, 0, 1)
    labels[:, 0] = icu_score

    # ── Mortality risk ────────────────────────────────────────────────
    extreme_spo2 = np.clip((92.0 - mean_spo2) / 10.0, 0, 1)
    extreme_hr   = np.clip((mean_hr - 130.0) / 40.0, 0, 1)
    labels[:, 1] = np.clip(0.5 * extreme_spo2 + 0.5 * extreme_hr, 0, 1)

    return labels


# ─────────────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────────────
def train(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    save_path: str = "models/gru_predictor.h5",
    epochs: int = 80,
    batch_size: int = 32,
) -> Tuple["tf.keras.Model", dict]:
    """
    Train the GRU predictor.

    Args:
        X_train: (N, T, F)  y_train: (N, 3)
        X_val:   (N, T, F)  y_val:   (N, 3)
        save_path: .h5 output.

    Returns:
        (model, history_dict)
    """
    import tensorflow as tf

    os.makedirs(Path(save_path).parent, exist_ok=True)
    model = build_gru_predictor(
        window_size=X_train.shape[1],
        n_features=X_train.shape[2],
    )
    model.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_auc", mode="max", patience=10,
            restore_best_weights=True, verbose=1,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            save_path, monitor="val_auc", mode="max",
            save_best_only=True, verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6
        ),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1,
    )
    return model, history.history


# ─────────────────────────────────────────────────────────────────────────
# Inference wrapper
# ─────────────────────────────────────────────────────────────────────────
class GRUPredictor:
    """
    Lambda-ready inference wrapper for the GRU risk predictor.

    Usage:
        predictor = GRUPredictor("models/gru_predictor.h5")
        result = predictor.predict(window_array)
    """

    # Risk thresholds → human-readable patient status
    _STATUS_RULES = [
        (lambda r: r["icu_probability"] > 0.75 or r["mortality_risk"] > 0.65,
         "Critical — Immediate Intervention Required"),
        (lambda r: r["icu_probability"] > 0.50 or r["deterioration_prob"] > 0.70,
         "High Cardiac Risk"),
        (lambda r: r["deterioration_prob"] > 0.45,
         "Deteriorating — Monitor Closely"),
        (lambda r: True,
         "Stable"),
    ]

    def __init__(self, model_path: str):
        import tensorflow as tf

        self._model = tf.keras.models.load_model(model_path, compile=False)
        logger.info("GRU Predictor loaded from %s", model_path)

    def predict(self, window: np.ndarray) -> Dict:
        """
        Args:
            window: np.ndarray shape (window_size, n_features) — normalized

        Returns:
            {
                "patient_status":    "High Cardiac Risk",
                "icu_probability":   0.81,
                "mortality_risk":    0.34,
                "deterioration_prob":0.67,
                "severity":          "critical",
            }
        """
        x = window[np.newaxis, ...]
        probs = self._model.predict(x, verbose=0)[0]   # (3,)

        result = {
            label: round(float(probs[i]), 4)
            for i, label in enumerate(RISK_LABELS)
        }

        # Derive patient status
        for condition, status in self._STATUS_RULES:
            if condition(result):
                result["patient_status"] = status
                break

        max_risk = float(np.max(probs))
        result["severity"] = (
            "critical" if max_risk > 0.75
            else "warning" if max_risk > 0.45
            else "normal"
        )

        return result
