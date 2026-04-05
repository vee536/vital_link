"""
VitalLink AI — Federated Learning Simulation (FedAvg)
=======================================================
Simulates federated training across three hospitals without
sharing raw patient data.  Only model weight deltas are aggregated.

Protocol
--------
1. Global model is broadcast to each hospital.
2. Each hospital trains locally for E epochs on its private dataset.
3. Hospitals send their updated weights to the central aggregator.
4. Aggregator performs Federated Averaging:

       w_global = Σ (n_k / N) * w_k
       where n_k = samples in hospital k, N = total samples

5. Steps 1–4 repeat for R communication rounds.

Privacy note
------------
In a real deployment, each hospital would additionally apply:
  - Differential Privacy (DP-SGD noise injection)
  - Secure Aggregation (secret sharing / homomorphic encryption)
This simulation focuses on the FedAvg logic only.
"""

from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Hospital data container
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class HospitalDataset:
    hospital_id: str
    X_train: np.ndarray       # (N, T, F)
    y_train: np.ndarray       # (N, n_classes)
    X_val: np.ndarray
    y_val: np.ndarray

    @property
    def n_samples(self) -> int:
        return len(self.X_train)


# ─────────────────────────────────────────────────────────────────────────
# Federated client (one per hospital)
# ─────────────────────────────────────────────────────────────────────────
class FederatedClient:
    """
    Represents a single hospital in the federation.

    Responsibilities:
      - Receive global model weights
      - Train locally for E epochs
      - Return updated weights (never raw data)
    """

    def __init__(
        self,
        hospital_id: str,
        dataset: HospitalDataset,
        model_builder_fn,          # callable() → compiled keras model
        local_epochs: int = 5,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
    ):
        self.hospital_id = hospital_id
        self.dataset = dataset
        self._model_builder_fn = model_builder_fn
        self.local_epochs = local_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate

        # Build once; weights are updated each round
        self._model = model_builder_fn()

    # ── public API ───────────────────────────────────────────────────────

    def set_weights(self, global_weights: List[np.ndarray]) -> None:
        """Receive the current global model weights."""
        self._model.set_weights(global_weights)

    def get_weights(self) -> List[np.ndarray]:
        return self._model.get_weights()

    def local_train(self) -> Dict:
        """
        Train for `local_epochs` on the hospital's private dataset.

        Returns a metrics dict (loss, accuracy, etc.) for monitoring.
        """
        import tensorflow as tf

        # Re-compile with fresh optimizer state each round to avoid
        # optimizer momentum carrying over between rounds
        self._model.compile(
            optimizer=tf.keras.optimizers.Adam(self.learning_rate),
            loss="binary_crossentropy",
            metrics=[
                tf.keras.metrics.BinaryAccuracy(name="accuracy"),
                tf.keras.metrics.AUC(name="auc", multi_label=True),
            ],
        )

        history = self._model.fit(
            self.dataset.X_train, self.dataset.y_train,
            validation_data=(self.dataset.X_val, self.dataset.y_val),
            epochs=self.local_epochs,
            batch_size=self.batch_size,
            verbose=0,
        )

        # Return final-epoch metrics
        metrics = {
            key: float(values[-1])
            for key, values in history.history.items()
        }
        metrics["n_samples"] = self.dataset.n_samples
        logger.info("[%s] local train done | auc=%.4f loss=%.4f",
                    self.hospital_id,
                    metrics.get("auc", 0), metrics.get("loss", 0))
        return metrics


# ─────────────────────────────────────────────────────────────────────────
# Central aggregator
# ─────────────────────────────────────────────────────────────────────────
class FedAvgAggregator:
    """
    Central server that orchestrates federated rounds.

    Algorithm: Federated Averaging (McMahan et al., 2017)
      w_{t+1} = Σ_k  (n_k / N) * w_k^{t+1}
    """

    def __init__(self, global_model: "tf.keras.Model"):
        self._global_model = global_model

    def get_global_weights(self) -> List[np.ndarray]:
        return self._global_model.get_weights()

    def aggregate(
        self,
        client_weights: List[List[np.ndarray]],
        client_sample_counts: List[int],
    ) -> List[np.ndarray]:
        """
        Weighted average of client weight lists.

        Args:
            client_weights:       List of weight lists from each client.
            client_sample_counts: Number of training samples per client.

        Returns:
            New global weight list (Federated Average).
        """
        total_samples = sum(client_sample_counts)
        fractions = [n / total_samples for n in client_sample_counts]

        # Weighted average layer-by-layer
        aggregated = []
        for layer_idx in range(len(client_weights[0])):
            layer_avg = sum(
                fractions[k] * client_weights[k][layer_idx]
                for k in range(len(client_weights))
            )
            aggregated.append(layer_avg)

        self._global_model.set_weights(aggregated)
        return aggregated

    def save_global_model(self, path: str) -> None:
        os.makedirs(Path(path).parent, exist_ok=True)
        self._global_model.save(path)
        logger.info("Global model saved → %s", path)


# ─────────────────────────────────────────────────────────────────────────
# Federation runner
# ─────────────────────────────────────────────────────────────────────────
class FederatedRunner:
    """
    Orchestrates multi-round federated training.

    Usage:
        runner = FederatedRunner(clients, aggregator, rounds=20)
        history = runner.run()
    """

    def __init__(
        self,
        clients: List[FederatedClient],
        aggregator: FedAvgAggregator,
        communication_rounds: int = 20,
        save_path: str = "models/federated_global.h5",
    ):
        self.clients = clients
        self.aggregator = aggregator
        self.communication_rounds = communication_rounds
        self.save_path = save_path
        self.history: List[Dict] = []

    def run(self) -> List[Dict]:
        """
        Execute all communication rounds and return per-round metrics.

        Returns:
            List of dicts, one per round, with per-hospital and global metrics.
        """
        logger.info(
            "Starting federated training | clients=%d rounds=%d",
            len(self.clients), self.communication_rounds,
        )

        for rnd in range(1, self.communication_rounds + 1):
            round_log = {"round": rnd, "hospitals": {}}

            # ── 1. Broadcast global weights ───────────────────────────────
            global_w = self.aggregator.get_global_weights()
            for client in self.clients:
                client.set_weights(copy.deepcopy(global_w))

            # ── 2. Parallel local training (sequential in simulation) ──────
            updated_weights = []
            sample_counts = []
            for client in self.clients:
                metrics = client.local_train()
                updated_weights.append(client.get_weights())
                sample_counts.append(client.dataset.n_samples)
                round_log["hospitals"][client.hospital_id] = metrics

            # ── 3. Aggregate ──────────────────────────────────────────────
            self.aggregator.aggregate(updated_weights, sample_counts)

            # ── 4. Compute mean client AUC as proxy for global performance ─
            aucs = [
                v.get("val_auc", v.get("auc", 0))
                for v in round_log["hospitals"].values()
            ]
            round_log["mean_auc"] = float(np.mean(aucs))
            self.history.append(round_log)

            logger.info(
                "Round %3d/%d | mean_auc=%.4f",
                rnd, self.communication_rounds, round_log["mean_auc"],
            )

        # Save final global model
        self.aggregator.save_global_model(self.save_path)
        logger.info("Federated training complete.")
        return self.history


# ─────────────────────────────────────────────────────────────────────────
# Synthetic hospital dataset generator (for simulation)
# ─────────────────────────────────────────────────────────────────────────
def generate_synthetic_hospital_data(
    hospital_id: str,
    n_patients: int = 500,
    window_size: int = 200,
    n_features: int = 5,
    n_classes: int = 6,
    random_seed: Optional[int] = None,
) -> HospitalDataset:
    """
    Generate synthetic vitals data mimicking one hospital's patient population.

    Each hospital has slightly different population characteristics (mean
    vitals shift) to simulate real-world distribution heterogeneity.
    """
    rng = np.random.default_rng(random_seed)

    # Hospital-specific population shift (non-iid simulation)
    shifts = {"hospital_a": 0.1, "hospital_b": -0.05, "hospital_c": 0.15}
    shift = shifts.get(hospital_id.lower(), 0.0)

    X = rng.standard_normal((n_patients, window_size, n_features)).astype(np.float32)
    X += shift   # population mean shift

    # Sparse multi-label targets (most patients normal)
    y = (rng.random((n_patients, n_classes)) > 0.85).astype(np.float32)
    y[:, 0] = 1.0 - np.any(y[:, 1:], axis=1).astype(np.float32)  # Normal if no condition

    split = int(0.8 * n_patients)
    return HospitalDataset(
        hospital_id=hospital_id,
        X_train=X[:split], y_train=y[:split],
        X_val=X[split:],   y_val=y[split:],
    )
