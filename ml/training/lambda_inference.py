"""
VitalLink AI — AWS Lambda Inference Handler
=============================================
Entry point for the AWS Lambda function that sits between
IoT Core / API Gateway and the WebSocket dashboard.

Lambda execution flow
---------------------
  IoT Core → Lambda (this file) → API Gateway WebSocket → Dashboard

This module:
  1. Receives a raw vitals payload from the existing Lambda handler
  2. Preprocesses vitals into a normalized time-series window
  3. Runs the three ML models in parallel:
       a. CNN-LSTM emergency classifier
       b. LSTM autoencoder anomaly detector
       c. GRU deterioration predictor
  4. Fuses results into a single structured AI output dict
  5. Returns the enriched payload for WebSocket broadcast

Cold-start optimisation
------------------------
Models are loaded at module level (outside handler) so they are
cached across warm Lambda invocations — this is critical for
the 2-second streaming cadence.

Environment variables
---------------------
MODEL_DIR           Path to model directory (default: /var/task/models)
WINDOW_SIZE         Sliding window depth (default: 200)
ANOMALY_THRESHOLD   Override file-based threshold (optional float)
LOG_LEVEL           Python logging level (default: INFO)

Deployment note
---------------
Package models into the Lambda deployment zip (< 250 MB limit) or
mount an EFS volume for larger model files.  Recommended: quantize
Keras models to TFLite for reduced size and faster inference.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

# ── logging ──────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("VitalLink.Lambda")

# ── path setup (for Lambda layer / EFS) ─────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.preprocess_vitals import VitalsWindowBuffer, parse_lambda_event, VITAL_KEYS

# ── config ───────────────────────────────────────────────────────────────
MODEL_DIR    = Path(os.environ.get("MODEL_DIR", str(ROOT / "models" / "saved")))
WINDOW_SIZE  = int(os.environ.get("WINDOW_SIZE", "200"))

CLASSIFIER_PATH = str(MODEL_DIR / "cnn_lstm_classifier.h5")
ANOMALY_PATH    = str(MODEL_DIR / "anomaly_detector.h5")
THRESHOLD_PATH  = str(MODEL_DIR / "anomaly_threshold.pkl")
GRU_PATH        = str(MODEL_DIR / "gru_predictor.h5")

# ─────────────────────────────────────────────────────────────────────────
# Module-level singletons (cached across warm invocations)
# ─────────────────────────────────────────────────────────────────────────
_classifier: Optional[Any]  = None
_anomaly:    Optional[Any]  = None
_gru:        Optional[Any]  = None
_window_buf: Optional[VitalsWindowBuffer] = None


def _load_models() -> None:
    """Lazy-load all ML models exactly once per Lambda container lifetime."""
    global _classifier, _anomaly, _gru, _window_buf

    if _window_buf is None:
        _window_buf = VitalsWindowBuffer(window_size=WINDOW_SIZE, stride=1)
        logger.info("Window buffer initialised (size=%d)", WINDOW_SIZE)

    if _classifier is None and MODEL_DIR.exists():
        try:
            from models.cnn_lstm_classifier import CNNLSTMPredictor
            _classifier = CNNLSTMPredictor(CLASSIFIER_PATH)
        except Exception as e:
            logger.warning("CNN-LSTM not loaded: %s", e)

    if _anomaly is None and MODEL_DIR.exists():
        try:
            from models.anomaly_detector import AnomalyDetector
            _anomaly = AnomalyDetector(ANOMALY_PATH, THRESHOLD_PATH)
        except Exception as e:
            logger.warning("Anomaly detector not loaded: %s", e)

    if _gru is None and MODEL_DIR.exists():
        try:
            from models.gru_predictor import GRUPredictor
            _gru = GRUPredictor(GRU_PATH)
        except Exception as e:
            logger.warning("GRU predictor not loaded: %s", e)


# Load at import time (outside handler) — cached on warm starts
_load_models()


# ─────────────────────────────────────────────────────────────────────────
# Inference fusion
# ─────────────────────────────────────────────────────────────────────────
def _run_inference(window: np.ndarray) -> Dict:
    """
    Run all three models and fuse their outputs into one AI result dict.

    Args:
        window: np.ndarray (window_size, n_features) — already normalised

    Returns:
        Fused prediction dict compatible with the WebSocket dashboard.
    """
    results: Dict = {
        "inference_ts": time.time(),
        "window_size":  WINDOW_SIZE,
    }

    # ── 1. Emergency Classifier ──────────────────────────────────────────
    if _classifier:
        try:
            cls_result = _classifier.predict(window)
            results["classification"] = cls_result
            results["conditions"]     = cls_result["conditions"]
            results["confidence"]     = cls_result["confidence"]
        except Exception as e:
            logger.error("Classifier inference error: %s", e)
            results["classification"] = {"error": str(e)}

    # ── 2. Anomaly Detection ─────────────────────────────────────────────
    if _anomaly:
        try:
            ano_result = _anomaly.detect(window)
            results["anomaly"] = ano_result
        except Exception as e:
            logger.error("Anomaly detector error: %s", e)
            results["anomaly"] = {"error": str(e)}

    # ── 3. GRU Risk Predictor ────────────────────────────────────────────
    if _gru:
        try:
            gru_result = _gru.predict(window)
            results["risk_prediction"]  = gru_result
            results["icu_probability"]  = gru_result.get("icu_probability", 0)
            results["mortality_risk"]   = gru_result.get("mortality_risk", 0)
        except Exception as e:
            logger.error("GRU predictor error: %s", e)
            results["risk_prediction"] = {"error": str(e)}

    # ── 4. Fuse into unified output ──────────────────────────────────────
    results.update(_fuse_predictions(results))
    return results


def _fuse_predictions(results: Dict) -> Dict:
    """
    Derive a single patient_status + severity from the three model outputs.

    Priority: GRU risk > CNN-LSTM conditions > anomaly score.
    """
    cls = results.get("classification", {})
    ano = results.get("anomaly", {})
    gru = results.get("risk_prediction", {})

    # Collect severity signals
    severities = []
    if isinstance(cls, dict) and "severity" in cls:
        severities.append(cls["severity"])
    if isinstance(ano, dict) and "severity" in ano:
        severities.append(ano["severity"])
    if isinstance(gru, dict) and "severity" in gru:
        severities.append(gru["severity"])

    # Escalate to worst observed severity
    severity_rank = {"critical": 3, "warning": 2, "normal": 1, "moderate": 1, "high": 2}
    severity = max(severities, key=lambda s: severity_rank.get(s, 0), default="unknown")

    patient_status = (
        gru.get("patient_status")
        or (", ".join(results.get("conditions", ["Normal"])))
    )

    return {
        "patient_status": patient_status,
        "severity":       severity,
        "icu_probability": results.get("icu_probability", 0),
        "anomaly_score":  ano.get("anomaly_score", 0) if isinstance(ano, dict) else 0,
    }


# ─────────────────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────────────────
def handler(event: Dict, context: Any) -> Dict:
    """
    AWS Lambda entry point.

    Expected invocation patterns:
      a) Direct IoT rule integration: event IS the vitals payload
      b) Via existing Lambda (pass-through): event["body"] = JSON string

    Returns the enriched payload that the caller should forward to
    API Gateway WebSocket (POST /@connections/{connectionId}).
    """
    start = time.time()

    # ── Parse incoming vitals ─────────────────────────────────────────────
    try:
        vitals = parse_lambda_event(event)
        patient_meta = (
            event.get("patient")
            or (json.loads(event["body"]) if isinstance(event.get("body"), str) else {})
               .get("patient", {})
        )
    except Exception as e:
        logger.error("Failed to parse event: %s | event=%s", e, event)
        return _error_response(f"Parse error: {e}")

    # ── Buffer & build window ─────────────────────────────────────────────
    window = _window_buf.push(vitals)

    if window is None:
        # Return a lightweight "buffering" response while window fills
        buffered = int(len(_window_buf._buffer))
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "buffering",
                "buffered": buffered,
                "required": WINDOW_SIZE,
                "patient":  patient_meta,
                "vitals":   vitals,
            }),
        }

    # ── Run ML inference ──────────────────────────────────────────────────
    ai_output = _run_inference(window)

    # ── Build final WebSocket payload ─────────────────────────────────────
    payload = {
        "type":           "ai_analysis",
        "patient":        patient_meta,
        "vitals":         vitals,
        "timestamp":      event.get("timestamp"),
        "ai": {
            "patient_status": ai_output.get("patient_status", "Unknown"),
            "severity":       ai_output.get("severity", "unknown"),
            "confidence":     ai_output.get("confidence", 0),
            "icu_probability":ai_output.get("icu_probability", 0),
            "anomaly_score":  ai_output.get("anomaly_score", 0),
            "conditions":     ai_output.get("conditions", []),
            "classification": ai_output.get("classification", {}),
            "anomaly":        ai_output.get("anomaly", {}),
            "risk_prediction":ai_output.get("risk_prediction", {}),
        },
        "inference_latency_ms": round((time.time() - start) * 1000, 1),
    }

    logger.info(
        "AI output | status=%s severity=%s icu=%.2f latency=%.1f ms",
        payload["ai"]["patient_status"],
        payload["ai"]["severity"],
        payload["ai"]["icu_probability"],
        payload["inference_latency_ms"],
    )

    return {
        "statusCode": 200,
        "body": json.dumps(payload),
    }


def _error_response(message: str) -> Dict:
    return {
        "statusCode": 500,
        "body": json.dumps({"error": message}),
    }


# ─────────────────────────────────────────────────────────────────────────
# Local smoke-test
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_event = {
        "patient": {"name": "John", "age": 45},
        "vitals": {
            "heart_rate":  92,
            "spo2":        94,
            "bp_sys":      140,
            "bp_dia":      90,
            "temperature": 37.5,
        },
        "timestamp": "2026-03-01T18:57:07",
    }
if __name__ == "__main__":
    test_event = {
        "patient": {"name": "John", "age": 45},
        "vitals": {
            "heart_rate":  110,
            "spo2":        93,
            "bp_sys":      165,
            "bp_dia":      95,
            "temperature": 38.2,
        },
        "timestamp": "2026-03-21T10:00:00",
    }
    result = handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))