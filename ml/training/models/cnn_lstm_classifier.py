"""
VitalLink AI — CNN-LSTM Emergency Classifier
=============================================
Multi-label classifier that detects emergency conditions
from a time-series window of vital signs.

Architecture
------------
Input  (batch, window_size, n_features)
  → Conv1D (64 filters, kernel 3) + ReLU
  → Conv1D (128 filters, kernel 3) + ReLU
  → MaxPooling1D (pool=2)
  → Dropout(0.3)
  → Conv1D (256 filters, kernel 3) + ReLU
  → MaxPooling1D (pool=2)
  → LSTM (128 units, return_sequences=True)
  → LSTM (64 units)
  → Dense (64) + ReLU + Dropout(0.4)
  → Dense (n_classes) + Sigmoid       ← multi-label output

Output classes (index → condition)
-----------------------------------
0  Normal
1  Hypoxia
2  Arrhythmia
3  Fever
4  Cardiac Risk
5  Shock
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Label schema ──────────────────────────────────────────────────────────
CONDITION_LABELS: List[str] = [
    "Normal",
    "Hypoxia",
    "Arrhythmia",
    "Fever",
    "Cardiac Risk",
    "Shock",
]
N_CLASSES: int = len(CONDITION_LABELS)


# ─────────────────────────────────────────────────────────────────────────
# Model builder
# ─────────────────────────────────────────────────────────────────────────
def build_cnn_lstm(
    window_size: int = 200,
    n_features: int = 5,
    n_classes: int = N_CLASSES,
    dropout_rate: float = 0.3,
    lstm_units: Tuple[int, int] = (128, 64),
) -> "tf.keras.Model":
    """
    Construct and return the compiled CNN-LSTM model.

    Args:
        window_size:  Number of timesteps per input window.
        n_features:   Number of vital signal channels (default 5).
        n_classes:    Number of output condition classes.
        dropout_rate: Dropout fraction after CNN and dense layers.
        lstm_units:   Units for the two LSTM layers.

    Returns:
        Compiled tf.keras.Model ready for training.
    """
    try:
        import tensorflow as tf
    except ImportError as e:
        raise ImportError("TensorFlow is required. Run: pip install tensorflow") from e

    inputs = tf.keras.Input(shape=(window_size, n_features), name="vitals_input")

    # ── Block 1: shallow CNN ─────────────────────────────────────────────
    x = tf.keras.layers.Conv1D(64, kernel_size=3, padding="same", activation="relu",
                                name="conv1")(inputs)
    x = tf.keras.layers.Conv1D(128, kernel_size=3, padding="same", activation="relu",
                                name="conv2")(x)
    x = tf.keras.layers.MaxPooling1D(pool_size=2, name="pool1")(x)
    x = tf.keras.layers.Dropout(dropout_rate, name="drop1")(x)

    # ── Block 2: deeper CNN ──────────────────────────────────────────────
    x = tf.keras.layers.Conv1D(256, kernel_size=3, padding="same", activation="relu",
                                name="conv3")(x)
    x = tf.keras.layers.MaxPooling1D(pool_size=2, name="pool2")(x)
    x = tf.keras.layers.Dropout(dropout_rate, name="drop2")(x)

    # ── Block 3: temporal modeling ───────────────────────────────────────
    x = tf.keras.layers.LSTM(lstm_units[0], return_sequences=True, name="lstm1")(x)
    x = tf.keras.layers.LSTM(lstm_units[1], return_sequences=False, name="lstm2")(x)

    # ── Block 4: classification head ─────────────────────────────────────
    x = tf.keras.layers.Dense(64, activation="relu", name="dense1")(x)
    x = tf.keras.layers.Dropout(0.4, name="drop3")(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="sigmoid", name="output")(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="VitalLink_CNN_LSTM")

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.AUC(name="auc", multi_label=True),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ],
    )
    logger.info("CNN-LSTM model built. Parameters: %d", model.count_params())
    return model


# ─────────────────────────────────────────────────────────────────────────
# Training helpers
# ─────────────────────────────────────────────────────────────────────────
def get_callbacks(checkpoint_path: str, patience: int = 10) -> list:
    """Standard training callbacks: early stopping + model checkpoint."""
    import tensorflow as tf

    return [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_auc", mode="max", patience=patience,
            restore_best_weights=True, verbose=1,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=checkpoint_path, monitor="val_auc",
            mode="max", save_best_only=True, verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5,
            min_lr=1e-6, verbose=1,
        ),
        tf.keras.callbacks.TensorBoard(
            log_dir=str(Path(checkpoint_path).parent / "tb_logs"),
            histogram_freq=1,
        ),
    ]


def train(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    save_path: str = "models/cnn_lstm_classifier.h5",
    epochs: int = 100,
    batch_size: int = 32,
    class_weights: Optional[Dict[int, float]] = None,
) -> Tuple["tf.keras.Model", dict]:
    """
    Full training pipeline for the CNN-LSTM classifier.

    Args:
        X_train, y_train: Training tensors.  X shape: (N, T, F)  y shape: (N, n_classes)
        X_val, y_val:     Validation tensors.
        save_path:        Where to save the best model (.h5).
        epochs:           Maximum training epochs.
        batch_size:       Mini-batch size.
        class_weights:    Optional per-class imbalance weights.

    Returns:
        (trained_model, history_dict)
    """
    import tensorflow as tf

    os.makedirs(Path(save_path).parent, exist_ok=True)
    model = build_cnn_lstm(
        window_size=X_train.shape[1],
        n_features=X_train.shape[2],
    )
    model.summary()

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=get_callbacks(save_path),
        class_weight=class_weights,
        verbose=1,
    )
    return model, history.history


# ─────────────────────────────────────────────────────────────────────────
# Evaluation helpers
# ─────────────────────────────────────────────────────────────────────────
def evaluate(
    model: "tf.keras.Model",
    X_test: np.ndarray,
    y_test: np.ndarray,
    threshold: float = 0.5,
) -> Dict:
    """
    Evaluate the trained model and return a full metrics report.

    Returns dict with per-class precision / recall / F1 + confusion matrices.
    """
    from sklearn.metrics import (
        classification_report,
        multilabel_confusion_matrix,
        roc_auc_score,
    )

    y_prob = model.predict(X_test, verbose=0)           # (N, n_classes)
    y_pred = (y_prob >= threshold).astype(int)

    report = classification_report(
        y_test, y_pred,
        target_names=CONDITION_LABELS,
        output_dict=True,
        zero_division=0,
    )

    try:
        auc_scores = roc_auc_score(y_test, y_prob, average=None)
        report["roc_auc_per_class"] = dict(zip(CONDITION_LABELS, auc_scores.tolist()))
        report["roc_auc_macro"] = float(np.mean(auc_scores))
    except ValueError:
        logger.warning("AUC computation failed (possible single-class issue in test set)")

    cm = multilabel_confusion_matrix(y_test, y_pred)
    report["confusion_matrices"] = {
        label: cm[i].tolist() for i, label in enumerate(CONDITION_LABELS)
    }

    logger.info("Evaluation complete. Macro AUC: %.4f", report.get("roc_auc_macro", 0))
    return report


# ─────────────────────────────────────────────────────────────────────────
# Inference (single window, no TF overhead on cold path)
# ─────────────────────────────────────────────────────────────────────────
class CNNLSTMPredictor:
    """
    Lightweight wrapper for Lambda inference.

    Loads the model once (module-level singleton pattern), then exposes
    a fast `predict` method that returns a structured prediction dict.
    """

    def __init__(self, model_path: str):
        import tensorflow as tf
        self._model = tf.keras.models.load_model(model_path, compile=False)
        logger.info("CNN-LSTM loaded from %s", model_path)

    def predict(
        self, window: np.ndarray, threshold: float = 0.5
    ) -> Dict:
        """
        Args:
            window: np.ndarray  shape (window_size, n_features) — already normalized
            threshold: classification threshold

        Returns:
            {
                "conditions":    ["Cardiac Risk", "Hypoxia"],
                "probabilities": {"Normal": 0.04, "Hypoxia": 0.87, ...},
                "severity":      "critical" | "warning" | "normal",
                "confidence":    0.87,
            }
        """
        x = window[np.newaxis, ...]          # (1, T, F)
        probs = self._model.predict(x, verbose=0)[0]  # (n_classes,)

        prob_map = {label: float(probs[i]) for i, label in enumerate(CONDITION_LABELS)}
        active = [label for label, p in prob_map.items() if p >= threshold and label != "Normal"]
        confidence = float(np.max(probs[1:]))  # max non-normal probability

        if confidence >= 0.75:
            severity = "critical"
        elif confidence >= 0.45:
            severity = "warning"
        else:
            severity = "normal"

        return {
            "conditions":    active if active else ["Normal"],
            "probabilities": prob_map,
            "severity":      severity,
            "confidence":    round(confidence, 4),
        }
