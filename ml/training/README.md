# VitalLink AI — Real-Time Patient Vital Monitoring ML Pipeline

> Production-grade ML system that plugs into the existing VitalLink AWS architecture to detect emergencies, anomalies, and predict patient deterioration in real time.

---

## Architecture Overview

```
Ambulance Simulator (Python, every 2s)
        ↓
  AWS IoT Core
        ↓
  AWS Lambda  ◄──── [ THIS SYSTEM INSERTS HERE ]
        ↓
  API Gateway WebSocket
        ↓
  React Dashboard
```

The AI pipeline is injected **inside** the Lambda function.  The existing Lambda calls `lambda_inference.handler()`, which enriches the vitals payload with AI predictions before forwarding it to the WebSocket.

---

## Project Structure

```
vital_link_ai/
│
├── preprocessing/
│   └── preprocess_vitals.py     Normalization, windowing, imputation
│
├── models/
│   ├── cnn_lstm_classifier.py   Emergency condition classifier
│   ├── anomaly_detector.py      LSTM Autoencoder anomaly detection
│   └── gru_predictor.py         GRU deterioration predictor
│
├── federated_learning/
│   └── fedavg.py                FedAvg simulation across 3 hospitals
│
├── training/
│   └── train_models.py          Master training pipeline
│
├── inference/
│   └── lambda_inference.py      AWS Lambda entry point
│
└── utils/
    └── helpers.py               Metrics, visualization, export, I/O
```

---

## ML Models

### 1. CNN-LSTM Emergency Classifier

**Purpose:** Multi-label classification of emergency conditions from a 200-timestep vital window.

**Architecture:**
```
Input (200, 5)
  → Conv1D(64)  → Conv1D(128) → MaxPool → Dropout
  → Conv1D(256) → MaxPool     → Dropout
  → LSTM(128, return_seq) → LSTM(64)
  → Dense(64)  → Dropout
  → Dense(6, sigmoid)    ← Sigmoid for multi-label
```

**Output classes:** Normal, Hypoxia, Arrhythmia, Fever, Cardiac Risk, Shock

**Key design decisions:**
- Sigmoid (not softmax) allows simultaneous multi-condition detection
- CNN extracts local temporal features; LSTM captures long-range dependencies
- Binary cross-entropy loss handles class imbalance naturally

---

### 2. LSTM Autoencoder — Anomaly Detector

**Purpose:** Detect rare/unseen physiological patterns by measuring reconstruction error.

**How it works:**
1. Trained **only** on normal vital sequences
2. At inference, abnormal sequences have high MSE (encoder cannot reconstruct them)
3. Threshold = 95th percentile MSE on normal validation set

**Architecture:**
```
Input (200, 5)
  → LSTM(128, seq) → LSTM(64)   [Encoder → latent z]
  → RepeatVector(200)            [Bridge]
  → LSTM(64, seq) → LSTM(128, seq)
  → TimeDistributed(Dense(5))    [Decoder → reconstruction]
```

**Output:**
```json
{
  "anomaly_score": 0.93,
  "reconstruction_mse": 0.0412,
  "is_anomaly": true,
  "status": "critical anomaly detected"
}
```

---

### 3. GRU Deterioration Predictor

**Purpose:** Predict patient deterioration within the next 10–30 minutes.

**Architecture:**
```
Input (200, 5)
  → GRU(128, seq) → Dropout
  → GRU(64,  seq) → Dropout
  → GRU(32)
  → Dense(64, relu) → Dropout
  → Dense(3, sigmoid)   ← [icu_prob, mortality_risk, deterioration_prob]
```

**Output:**
```json
{
  "patient_status": "High Cardiac Risk",
  "icu_probability": 0.81,
  "mortality_risk": 0.34,
  "deterioration_prob": 0.67,
  "severity": "critical"
}
```

**Why GRU over LSTM?** GRU has fewer parameters (no cell state), trains faster, and performs comparably on shorter sequences — reducing Lambda cold-start latency.

---

### 4. Federated Learning — FedAvg

**Purpose:** Train a shared global model across hospitals without sharing patient data.

**Protocol:**
```
Round t:
  1. Broadcast w_global → Hospital A, B, C
  2. Each hospital trains locally for E=5 epochs
  3. Hospitals return updated weights (no raw data)
  4. Aggregator: w_global = Σ (n_k / N) * w_k
  5. Repeat for R=20 rounds
```

**Privacy note:** In production, add DP-SGD noise injection and secure aggregation (homomorphic encryption / secret sharing).

---

## AI Output Schema

The Lambda returns this enriched payload to the WebSocket dashboard:

```json
{
  "type": "ai_analysis",
  "patient": { "name": "John", "age": 45 },
  "vitals": { "heart_rate": 92, "spo2": 94, ... },
  "ai": {
    "patient_status": "High Cardiac Risk",
    "severity": "critical",
    "confidence": 0.92,
    "icu_probability": 0.81,
    "anomaly_score": 0.14,
    "conditions": ["Cardiac Risk"],
    "classification": { ... },
    "anomaly": { ... },
    "risk_prediction": { ... }
  },
  "inference_latency_ms": 38.4
}
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Train all models (synthetic data)
```bash
python training/train_models.py --mode all --patients 2000 --window 200
```

Train individual models:
```bash
python training/train_models.py --mode classifier
python training/train_models.py --mode anomaly
python training/train_models.py --mode gru
python training/train_models.py --mode federated
```

Trained models are saved to `models/saved/`.

### 3. Test Lambda inference locally
```bash
python inference/lambda_inference.py
```

### 4. Integrate with existing Lambda

In your **existing** Lambda handler, replace the direct WebSocket push with:

```python
import sys
sys.path.insert(0, '/opt/python')  # Lambda layer path

from inference.lambda_inference import handler as ai_handler

def lambda_handler(event, context):
    # ... existing IoT parsing ...

    # Call VitalLink AI
    ai_response = ai_handler(event, context)

    # Forward enriched payload to WebSocket
    import json, boto3
    body = json.loads(ai_response['body'])
    apigw = boto3.client('apigatewaymanagementapi', endpoint_url=WS_ENDPOINT)
    apigw.post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps(body).encode()
    )
```

---

## Data Format

### Real patient data (CSV)
```
timestamp,heart_rate,spo2,bp_sys,bp_dia,temperature
2026-03-01T18:57:07,92,94,140,90,37.5
```

Load with:
```python
from utils.helpers import load_records_from_csv
records = load_records_from_csv("data/patient_vitals.csv")
```

### S3 data lake (JSON-lines)
```python
from utils.helpers import load_records_from_s3
records = load_records_from_s3("vitallink-data", "patients/2026/03/vitals.jsonl")
```

---

## Deployment

### Lambda packaging
```bash
# Install dependencies into package dir
pip install -r requirements.txt -t lambda_package/

# Copy source
cp -r vital_link_ai/ lambda_package/
cp -r models/saved/  lambda_package/models/

# Zip for upload
cd lambda_package && zip -r ../vitallink_ai.zip .
```

### Model size optimization (TFLite)
```python
from utils.helpers import export_tflite
export_tflite("models/saved/cnn_lstm_classifier.h5",
              "models/saved/cnn_lstm_classifier.tflite",
              quantize=True)
```
Typical size reduction: ~75% with INT8 quantization.

### Lambda environment variables
| Variable | Default | Description |
|---|---|---|
| `MODEL_DIR` | `/var/task/models` | Path to saved models |
| `WINDOW_SIZE` | `200` | Timesteps per inference window (~6.6 min) |
| `LOG_LEVEL` | `INFO` | Python logging level |

### Recommended Lambda config
| Setting | Value |
|---|---|
| Memory | 1024 MB (TensorFlow needs headroom) |
| Timeout | 30 seconds |
| Architecture | x86_64 (best TF support) |
| Runtime | Python 3.11 |

---

## Performance Targets

| Metric | Target |
|---|---|
| Inference latency (warm) | < 50 ms |
| Inference latency (cold start) | < 3 s |
| CNN-LSTM macro AUC | > 0.85 |
| Anomaly detection precision | > 0.80 |
| GRU deterioration AUC | > 0.82 |
| Real-time throughput | ≥ 0.5 Hz (1 per 2 s) |

---

## Clinical Notes

- All thresholds are configurable — consult clinical staff before deploying
- Models output **probabilities**, not diagnoses — always present with confidence
- The sliding window buffer fills over ~6.6 minutes (200 × 2 s); the system returns a `buffering` status until then
- Federated models trained across hospitals are more robust to population shift
