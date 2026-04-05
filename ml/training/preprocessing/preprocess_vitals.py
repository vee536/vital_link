"""
VitalLink AI — Preprocessing Module (v2 — Real Dataset)
=========================================================
Updated normalization constants derived from healthcare_monitoring_dataset.csv.

Key changes from v1
--------------------
* VITAL_STATS updated with dataset-derived mean/std/min/max
* Blood Pressure parsed from "sys/dia" string format
* Respiratory Rate and Glucose columns intentionally excluded:
    - Respiratory Rate is absent from the 5-feature inference schema
    - Glucose excluded per project requirements
* Inference input shape UNCHANGED: (window_size, 5)

Feature order (must match lambda_inference.py exactly)
-------------------------------------------------------
Index 0 — heart_rate
Index 1 — spo2
Index 2 — bp_sys
Index 3 — bp_dia
Index 4 — temperature
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import interp1d

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Normalization constants derived from healthcare_monitoring_dataset.csv
# ─────────────────────────────────────────────────────────────────────────
VITAL_STATS: Dict[str, Dict[str, float]] = {
    "heart_rate":  {"mean": 69.47, "std": 10.03, "min": 30.0,  "max": 109.0},
    "spo2":        {"mean": 97.51, "std":  1.05, "min": 93.0,  "max": 101.0},
    "bp_sys":      {"mean": 119.70,"std": 15.02, "min": 62.0,  "max": 187.0},
    "bp_dia":      {"mean":  79.37,"std":  9.92, "min": 43.0,  "max": 116.0},
    "temperature": {"mean":  36.60,"std":  0.50, "min": 34.5,  "max":  38.4},
}

VITAL_KEYS: List[str] = ["heart_rate", "spo2", "bp_sys", "bp_dia", "temperature"]
N_FEATURES: int = len(VITAL_KEYS)   # 5


# ─────────────────────────────────────────────────────────────────────────
# Normalizer
# ─────────────────────────────────────────────────────────────────────────
def _resolve_aliases(vitals: Dict) -> Dict:
    """Map verbose dataset column names to canonical short keys.
    Also parses Blood Pressure from 'sys/dia' string format."""
    resolved = dict(vitals)
    if "heart_rate" not in resolved and "Heart Rate (bpm)" in resolved:
        resolved["heart_rate"] = resolved.pop("Heart Rate (bpm)")
    if "spo2" not in resolved and "Blood Oxygen Level (SpO2 %)" in resolved:
        resolved["spo2"] = resolved.pop("Blood Oxygen Level (SpO2 %)")
    if "temperature" not in resolved and "Body Temperature (°C)" in resolved:
        resolved["temperature"] = resolved.pop("Body Temperature (°C)")
    if "bp_sys" not in resolved or "bp_dia" not in resolved:
        raw_bp = resolved.get("Blood Pressure (mmHg)")
        if raw_bp and isinstance(raw_bp, str) and "/" in raw_bp:
            parts = raw_bp.split("/")
            resolved["bp_sys"] = float(parts[0])
            resolved["bp_dia"] = float(parts[1])
    return resolved


class VitalsNormalizer:
    """Z-score normalization using dataset-calibrated statistics."""

    def normalize_sample(self, vitals: Dict[str, float]) -> np.ndarray:
        """Convert raw vitals dict → normalized float32 array shape (5,)."""
        vitals = _resolve_aliases(vitals)
        vec = np.zeros(N_FEATURES, dtype=np.float32)
        for i, key in enumerate(VITAL_KEYS):
            raw = vitals.get(key)
            stats = VITAL_STATS[key]
            if raw is None:
                vec[i] = 0.0
            else:
                clipped = np.clip(float(raw), stats["min"], stats["max"])
                vec[i] = (clipped - stats["mean"]) / stats["std"]
        return vec

    def denormalize_sample(self, vec: np.ndarray) -> Dict[str, float]:
        """Inverse transform: normalized array → raw vitals dict."""
        return {
            key: float(vec[i] * VITAL_STATS[key]["std"] + VITAL_STATS[key]["mean"])
            for i, key in enumerate(VITAL_KEYS)
        }


# ─────────────────────────────────────────────────────────────────────────
# Sliding-window buffer (stateful — used by Lambda at inference time)
# ─────────────────────────────────────────────────────────────────────────
class VitalsWindowBuffer:
    """Rolling window buffer. Interface UNCHANGED from v1."""

    def __init__(self, window_size: int = 200, stride: int = 1):
        self.window_size = window_size
        self.stride = stride
        self._buffer: Deque[np.ndarray] = deque(maxlen=window_size)
        self._normalizer = VitalsNormalizer()
        self._tick = 0

    def push(self, vitals: Dict[str, float]) -> Optional[np.ndarray]:
        normed = self._normalizer.normalize_sample(vitals)
        self._buffer.append(normed)
        self._tick += 1
        if len(self._buffer) == self.window_size and (self._tick % self.stride == 0):
            return np.array(self._buffer, dtype=np.float32)
        return None

    def is_ready(self) -> bool:
        return len(self._buffer) == self.window_size

    def get_partial_window(self) -> np.ndarray:
        arr = np.array(self._buffer, dtype=np.float32)
        pad = self.window_size - len(arr)
        if pad > 0:
            arr = np.vstack([np.zeros((pad, N_FEATURES), dtype=np.float32), arr])
        return arr

    def reset(self) -> None:
        self._buffer.clear()
        self._tick = 0


# ─────────────────────────────────────────────────────────────────────────
# Window-level label generator
# ─────────────────────────────────────────────────────────────────────────
def _label_window(hr, spo2, temp, sys_bp) -> List[int]:
    """
    Multi-label binary flags for one vital-sign window.

    Thresholds calibrated to healthcare_monitoring_dataset.csv distribution:
      Hypoxia      — >20% of window readings have SpO2 < 97%
      Arrhythmia   — window HR std > 10.5 bpm
      Fever        — any reading above 38.0 °C
      Cardiac Risk — max SysBP > 160 mmHg OR >5% readings HR < 50 bpm
      Shock        — not present in this dataset (always 0)

    Dataset label prevalence (stride=1, 9801 windows):
      Normal: 32.3%  |  Hypoxia: 3.9%  |  Arrhythmia: 15.9%
      Fever: 25.0%   |  Cardiac Risk: 52.4%  |  Shock: 0%
    """
    hypoxia = bool(np.mean(spo2 < 97) > 0.20)
    arrhyth = bool(np.std(hr) > 10.5)
    fever   = bool(np.max(temp) > 38.0)
    cardiac = bool(np.max(sys_bp) > 160.0 or np.mean(hr < 50) > 0.05)
    any_abn = hypoxia or arrhyth or fever or cardiac
    return [int(not any_abn), int(hypoxia), int(arrhyth), int(fever), int(cardiac), 0]


# ─────────────────────────────────────────────────────────────────────────
# Batch dataset builder
# ─────────────────────────────────────────────────────────────────────────
class VitalsDatasetBuilder:
    """Build (X, y) tensors from a pandas DataFrame."""

    def __init__(self, window_size: int = 200, stride: int = 1):
        self.window_size = window_size
        self.stride = stride

    def build_from_dataframe(self, df) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build normalized windows + multi-label targets.

        Expects df to have bp_sys / bp_dia already split
        (call dataset_loader.parse_blood_pressure(df) first).

        Returns:
            X      → (N, window_size, 5) float32
            labels → (N, 6) float32
        """
        feature_col_map = {
            "heart_rate":  "Heart Rate (bpm)",
            "spo2":        "Blood Oxygen Level (SpO2 %)",
            "bp_sys":      "bp_sys",
            "bp_dia":      "bp_dia",
            "temperature": "Body Temperature (°C)",
        }

        raw = np.zeros((len(df), N_FEATURES), dtype=np.float32)
        for i, key in enumerate(VITAL_KEYS):
            col = feature_col_map[key]
            raw[:, i] = df[col].values.astype(np.float32)

        # Interpolate NaN (defensive)
        for col_idx in range(N_FEATURES):
            if np.any(np.isnan(raw[:, col_idx])):
                idx = np.arange(len(raw))
                valid = ~np.isnan(raw[:, col_idx])
                f = interp1d(idx[valid], raw[valid, col_idx], fill_value="extrapolate")
                raw[:, col_idx] = f(idx)

        # Z-score normalize
        normed = np.zeros_like(raw)
        for i, key in enumerate(VITAL_KEYS):
            s = VITAL_STATS[key]
            clipped = np.clip(raw[:, i], s["min"], s["max"])
            normed[:, i] = (clipped - s["mean"]) / s["std"]

        # Sliding windows
        hr_raw   = df["Heart Rate (bpm)"].values.astype(float)
        spo2_raw = df["Blood Oxygen Level (SpO2 %)"].values.astype(float)
        temp_raw = df["Body Temperature (°C)"].values.astype(float)
        sys_raw  = df["bp_sys"].values.astype(float)

        windows, label_list = [], []
        n = len(normed)
        for start in range(0, n - self.window_size + 1, self.stride):
            end = start + self.window_size
            windows.append(normed[start:end])
            label_list.append(_label_window(
                hr_raw[start:end], spo2_raw[start:end],
                temp_raw[start:end], sys_raw[start:end],
            ))

        X = np.stack(windows, axis=0)
        y = np.array(label_list, dtype=np.float32)

        cond_names = ["Normal","Hypoxia","Arrhythmia","Fever","Cardiac Risk","Shock"]
        prevalence = {n: f"{v:.1%}" for n, v in zip(cond_names, y.mean(axis=0).tolist())}
        logger.info("Dataset built: X=%s  y=%s", X.shape, y.shape)
        logger.info("Label prevalence: %s", prevalence)
        return X, y

    # Legacy interface (v1 compatibility)
    def build(self, records: List[Dict], label_key: Optional[str] = None):
        normed = np.array(
            [VitalsNormalizer().normalize_sample(r.get("vitals", r)) for r in records],
            dtype=np.float32,
        )
        windows, label_windows = [], []
        n = len(normed)
        for start in range(0, n - self.window_size + 1, self.stride):
            windows.append(normed[start : start + self.window_size])
            if label_key:
                label_windows.append(records[start + self.window_size - 1].get(label_key))
        X = np.stack(windows, axis=0)
        labels = np.array(label_windows) if label_key else None
        return X, labels


# ─────────────────────────────────────────────────────────────────────────
# Lambda event parser (unchanged — inference compatibility)
# ─────────────────────────────────────────────────────────────────────────
def parse_lambda_event(event: Dict) -> Dict[str, float]:
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)
    vitals = body.get("vitals", body)
    resolved = _resolve_aliases({k: vitals[k] for k in vitals})
    return {k: float(resolved[k]) for k in VITAL_KEYS if k in resolved}
