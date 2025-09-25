import time
import wfdb
import random
import json
import os
import signal
import sys

# ----------------------------
# One-time patient information
# ----------------------------
patient_name = input("Enter patient name: ")
patient_age = input("Enter patient age: ")

print(f"\n🚑 Starting vitals stream for {patient_name}, Age: {patient_age}")
print("-" * 70)

# ----------------------------
# Temporary storage file
# ----------------------------
filename = "patient_vitals_temp.json"

# Start with empty list
with open(filename, "w") as f:
    json.dump([], f)

# ----------------------------
# Graceful exit handler (auto-clear file)
# ----------------------------
def cleanup_and_exit(sig=None, frame=None):
    if os.path.exists(filename):
        os.remove(filename)
        print(f"\n🧹 Temporary file '{filename}' deleted. Data cleared for compliance.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, cleanup_and_exit)  # Kill signal

# ----------------------------
# Load ECG record (PhysioNet sample)
# ----------------------------
record = wfdb.rdrecord('100', pn_dir='mitdb')

# ----------------------------
# Loop through each ECG sample and simulate vitals
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

    # Print live vitals
    print(
        f"{vitals_entry['timestamp']} | "
        f"Patient: {patient_name} | Age: {patient_age} | "
        f"HR: {vitals_entry['vitals']['heart_rate']} bpm | "
        f"SpO₂: {vitals_entry['vitals']['spo2']}% | "
        f"BP: {vitals_entry['vitals']['bp_sys']}/{vitals_entry['vitals']['bp_dia']} mmHg"
    )

    # Append to JSON file
    with open(filename, "r+") as f:
        data = json.load(f)
        data.append(vitals_entry)
        f.seek(0)
        json.dump(data, f, indent=2)

    time.sleep(1)  # 1-second updates
