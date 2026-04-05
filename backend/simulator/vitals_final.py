import time
import random
import json
import csv
import os
import signal
import sys
import ssl
from datetime import datetime
import paho.mqtt.client as mqtt

# ---------------------------- Patient Info ----------------------------
patient_name = input("Enter patient name: ")
patient_age  = input("Enter patient age: ")

# ---------------------------- Ambulance Selection ----------------------------
print("\nHow many ambulances do you want to simulate?")
print("Press Enter to use default (4), or type a number:")
num_input = input("Number of ambulances: ").strip()
NUM_AMBULANCES = int(num_input) if num_input.isdigit() and int(num_input) > 0 else 4
AMBULANCE_IDS  = [f"ambulance{i+1}" for i in range(NUM_AMBULANCES)]

print(f"\n🚑 Starting vitals stream for {patient_name}, Age: {patient_age}")
print(f"🚑 Simulating {NUM_AMBULANCES} ambulances: {', '.join(AMBULANCE_IDS)}")
print("-" * 70)

# ---------------------------- Temporary JSON ----------------------------
TEMP_FILE = "patient_vitals_temp.json"
with open(TEMP_FILE, "w") as f:
    json.dump([], f)

def cleanup_and_exit(sig=None, frame=None):
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
        print(f"\n🧹 Temporary file '{TEMP_FILE}' deleted. Data cleared.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

# ---------------------------- MQTT / AWS IoT Setup ----------------------------
AWS_ENDPOINT = "aj3jbl23441fa-ats.iot.eu-north-1.amazonaws.com"
AWS_PORT     = 8883

# Certificate paths — matched exactly to files in the simulator folder
CA_PATH   = "AmazonRootCA1.pem"
CERT_PATH = "device-cert.pem.crt"
KEY_PATH  = "device-private.pem.key"

client = mqtt.Client()
client.tls_set(
    ca_certs=CA_PATH,
    certfile=CERT_PATH,
    keyfile=KEY_PATH,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
connected_flag = False

def on_connect(client, userdata, flags, rc):
    global connected_flag
    if rc == 0:
        connected_flag = True
        print("✅ Connected to AWS IoT Core")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    global connected_flag
    connected_flag = False
    print("⚠️ Disconnected from AWS IoT Core")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    print("Connecting to AWS IoT Core...")
    client.connect(AWS_ENDPOINT, AWS_PORT, keepalive=60)
    client.loop_start()
except Exception as e:
    print(f"❌ Initial connection error: {e}")

# ---------------------------- CSV Backup ----------------------------
CSV_FILE = "vitals_log.csv"
with open(CSV_FILE, "a", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    if csvfile.tell() == 0:
        writer.writerow([
            "timestamp", "ambulance_id", "patient_name", "patient_age",
            "heart_rate", "spo2", "bp_sys", "bp_dia", "temperature", "alerts"
        ])

# ---------------------------- Dataset Loading ----------------------------
DATASET_FILE = "healthcare_monitoring_dataset.csv"
dataset_rows = []

def load_dataset(filepath):
    """Load the healthcare CSV dataset into memory.
    Opens with utf-8 encoding to correctly handle special characters
    like the degree symbol (°) in 'Body Temperature (°C)'.
    """
    rows = []
    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        if rows:
            print(f"✅ Dataset loaded: {len(rows)} records from '{filepath}'")
        else:
            print(f"⚠️  Dataset file '{filepath}' is empty. Falling back to random vitals.")
    except FileNotFoundError:
        print(f"⚠️  Dataset file '{filepath}' not found. Falling back to random vitals.")
    except Exception as e:
        print(f"⚠️  Error loading dataset: {e}. Falling back to random vitals.")
    return rows

dataset_rows = load_dataset(DATASET_FILE)

# Confirm vitals source at startup
if dataset_rows:
    print(f"📊 Vitals source: DATASET ({len(dataset_rows)} rows)")
else:
    print("⚠️  Vitals source: RANDOM FALLBACK")

# ---------------------------- Vital Generation ----------------------------
def vitals_from_dataset(row):
    """Extract vitals from a dataset row dict."""
    hr   = int(float(row["Heart Rate (bpm)"]))
    spo2 = int(float(row["Blood Oxygen Level (SpO2 %)"]))
    temp = round(float(row["Body Temperature (\u00b0C)"]), 1)  # °C as unicode

    # Blood Pressure stored as "120/80" — parse into systolic/diastolic
    bp_str   = row["Blood Pressure (mmHg)"]
    bp_parts = bp_str.strip().split("/")
    bp_sys   = int(bp_parts[0])
    bp_dia   = int(bp_parts[1])

    return hr, spo2, bp_sys, bp_dia, temp

def generate_vitals_random():
    """Fallback: generate random vitals when dataset is unavailable."""
    hr     = random.randint(45, 130)
    spo2   = random.randint(85, 100)
    bp_sys = random.randint(90, 160)
    bp_dia = random.randint(50, 100)
    temp   = round(random.uniform(34.0, 40.0), 1)
    return hr, spo2, bp_sys, bp_dia, temp

def generate_vitals():
    """Generate vitals from dataset row if available, else use random fallback."""
    if dataset_rows:
        row = random.choice(dataset_rows)
        return vitals_from_dataset(row)
    else:
        return generate_vitals_random()

# ---------------------------- Alert Detection ----------------------------
def check_alerts(hr, spo2, bp_sys, bp_dia, temp):
    alerts = []
    if hr < 50:       alerts.append("Bradycardia (Low HR)")
    elif hr > 120:    alerts.append("Tachycardia (High HR)")
    if spo2 < 92:     alerts.append("Low Oxygen Level")
    if bp_sys > 140:  alerts.append("High Systolic BP")
    if bp_dia < 60:   alerts.append("Low Diastolic BP")
    if temp < 35:     alerts.append("Hypothermia")
    elif temp > 38.5: alerts.append("Fever Detected")
    return alerts

# ---------------------------- Main Loop ----------------------------
print("\n🟢 Starting simulation loop... Press Ctrl+C to stop.\n")
print("-" * 70)

while True:
    for ambulance_id in AMBULANCE_IDS:
        topic = f"vital-link/{ambulance_id}/vitals"

        hr, spo2, bp_sys, bp_dia, temp = generate_vitals()
        alerts    = check_alerts(hr, spo2, bp_sys, bp_dia, temp)
        timestamp = datetime.utcnow().isoformat()

        data_packet = {
            "ambulance_id": ambulance_id,
            "patient": {"name": patient_name, "age": patient_age},
            "vitals": {
                "heart_rate":  hr,
                "spo2":        spo2,
                "bp_sys":      bp_sys,
                "bp_dia":      bp_dia,
                "temperature": temp
            },
            "alerts":    alerts,
            "timestamp": timestamp
        }

        # Publish to MQTT
        if connected_flag:
            try:
                client.publish(topic, json.dumps(data_packet), qos=1)
                print(f"📡 [{ambulance_id}] HR:{hr} SpO2:{spo2} BP:{bp_sys}/{bp_dia} Temp:{temp}°C | Alerts: {alerts if alerts else 'None'}")
            except Exception as e:
                print(f"⚠️  [{ambulance_id}] Publish error: {e}")
        else:
            print(f"⏳ [{ambulance_id}] Waiting for AWS connection...")

        # Append to JSON temp file
        with open(TEMP_FILE, "r+", encoding="utf-8") as f:
            data_list = json.load(f)
            data_list.append(data_packet)
            f.seek(0)
            json.dump(data_list, f, indent=2)

        # Write to CSV log
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                timestamp, ambulance_id, patient_name, patient_age,
                hr, spo2, bp_sys, bp_dia, temp, "; ".join(alerts)
            ])

    print("-" * 70)
    time.sleep(2)  # adjust interval as needed
