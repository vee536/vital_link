import time
import wfdb
import random
import json
import requests

# ----------------------------
# Config (mock hospital API)
# ----------------------------
CLOUD_API = "http://example.com/api/vitals"  # replace with real endpoint

# ----------------------------
# Patient info
# ----------------------------
patient_name = input("Enter patient name: ")
patient_age = input("Enter patient age: ")

print(f"\n🚑 Streaming vitals for {patient_name}, Age: {patient_age}")
print("-" * 70)

# ----------------------------
# Load ECG record (PhysioNet)
# ----------------------------
record = wfdb.rdrecord('100', pn_dir='mitdb')

# ----------------------------
# Stream loop
# ----------------------------
for val in record.p_signal:
    vitals_entry = {
        "patient": {
            "name": patient_name,
            "age": patient_age
        },
        "vitals": {
            "heart_rate": random.randint(60, 100),   # bpm
            "spo2": random.randint(95, 99),          # %
            "bp_sys": random.randint(110, 130),      # mmHg
            "bp_dia": random.randint(70, 85)         # mmHg
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Print locally
    print(
        f"{vitals_entry['timestamp']} | "
        f"HR: {vitals_entry['vitals']['heart_rate']} bpm | "
        f"SpO₂: {vitals_entry['vitals']['spo2']}% | "
        f"BP: {vitals_entry['vitals']['bp_sys']}/{vitals_entry['vitals']['bp_dia']} mmHg"
    )

    # Send to cloud (POST request)
    try:
        response = requests.post(CLOUD_API, json=vitals_entry, timeout=2)
        if response.status_code == 200:
            print("✅ Sent to cloud")
        else:
            print(f"⚠️ Failed to send: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending to cloud: {e}")

    time.sleep(1)  # 1-second updates
