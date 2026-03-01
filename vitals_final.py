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
patient_age = input("Enter patient age: ")

print(f"\n🚑 Starting vitals stream for {patient_name}, Age: {patient_age}")
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

# ---------------------------- MQTT Setup ----------------------------
AWS_ENDPOINT = "aj3jbl23441fa-ats.iot.eu-north-1.amazonaws.com"
AWS_PORT = 8883
TOPIC = "vital-link/ambulance1/vitals"

CA_PATH = "AmazonRootCA1.pem"
CERT_PATH = "device-cert.pem.crt"
KEY_PATH = "device-private.pem.key"

client = mqtt.Client()
client.tls_set(ca_certs=CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)
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
with open(CSV_FILE, "a", newline="") as csvfile:
    writer = csv.writer(csvfile)
    if csvfile.tell() == 0:
        writer.writerow(["timestamp","patient_name","patient_age","heart_rate","spo2","bp_sys","bp_dia","temperature","alerts"])

# ---------------------------- Vital Simulation ----------------------------
def generate_vitals():
    hr = random.randint(45, 130)
    spo2 = random.randint(85, 100)
    bp_sys = random.randint(90, 160)
    bp_dia = random.randint(50, 100)
    temp = round(random.uniform(34.0, 40.0), 1)
    return hr, spo2, bp_sys, bp_dia, temp

def check_alerts(hr, spo2, bp_sys, bp_dia, temp):
    alerts = []
    if hr < 50: alerts.append("Bradycardia (Low HR)")
    elif hr > 120: alerts.append("Tachycardia (High HR)")
    if spo2 < 92: alerts.append("Low Oxygen Level")
    if bp_sys > 140: alerts.append("High Systolic BP")
    if bp_dia < 60: alerts.append("Low Diastolic BP")
    if temp < 35: alerts.append("Hypothermia")
    elif temp > 38.5: alerts.append("Fever Detected")
    return alerts

# ---------------------------- Main Loop ----------------------------
while True:
    hr, spo2, bp_sys, bp_dia, temp = generate_vitals()
    alerts = check_alerts(hr, spo2, bp_sys, bp_dia, temp)
    timestamp = datetime.utcnow().isoformat()

    data_packet = {
        "patient": {"name": patient_name, "age": patient_age},
        "vitals": {
            "heart_rate": hr,
            "spo2": spo2,
            "bp_sys": bp_sys,
            "bp_dia": bp_dia,
            "temperature": temp
        },
        "alerts": alerts,
        "timestamp": timestamp
    }

    # Publish to MQTT
    if connected_flag:
        try:
            client.publish(TOPIC, json.dumps(data_packet), qos=1)
            print(f"📡 Published: {data_packet}")
        except Exception as e:
            print(f" Publish error: {e}")
    else:
        print(" Waiting for AWS connection...")

    # Append to JSON temp file
    with open(TEMP_FILE, "r+") as f:
        data_list = json.load(f)
        data_list.append(data_packet)
        f.seek(0)
        json.dump(data_list, f, indent=2)

    # Write to CSV
    with open(CSV_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, patient_name, patient_age, hr, spo2, bp_sys, bp_dia, temp, "; ".join(alerts)])

    time.sleep(2)  # adjust interval as needed
