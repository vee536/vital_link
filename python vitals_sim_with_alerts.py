import time
import random
import json
from datetime import datetime

def generate_vitals():
    """Simulate vital signs with realistic ranges"""
    heart_rate = random.randint(45, 130)      # bpm
    spo2 = random.randint(85, 100)            # %
    bp_sys = random.randint(90, 160)          # mmHg
    bp_dia = random.randint(50, 100)          # mmHg
    temperature = round(random.uniform(34.0, 40.0), 1)  # °C
    return heart_rate, spo2, bp_sys, bp_dia, temperature

def check_alerts(hr, spo2, bp_sys, bp_dia, temp):
    """Return list of alerts based on thresholds"""
    alerts = []

    if hr < 50:
        alerts.append("Bradycardia (Low HR)")
    elif hr > 120:
        alerts.append("Tachycardia (High HR)")

    if spo2 < 92:
        alerts.append("Low Oxygen Level")

    if bp_sys > 140:
        alerts.append("High Systolic BP")
    if bp_dia < 60:
        alerts.append("Low Diastolic BP")

    if temp < 35:
        alerts.append("Hypothermia")
    elif temp > 38.5:
        alerts.append("Fever Detected")

    return alerts

def main():
    patient_name = input("Enter patient name: ")
    patient_age = input("Enter patient age: ")

    while True:
        hr, spo2, bp_sys, bp_dia, temp = generate_vitals()
        alerts = check_alerts(hr, spo2, bp_sys, bp_dia, temp)

        # Prepare data packet
        packet = {
            "patient": {"name": patient_name, "age": patient_age},
            "vitals": {
                "heart_rate": hr,
                "spo2": spo2,
                "bp_sys": bp_sys,
                "bp_dia": bp_dia,
                "temperature": temp
            },
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Print to console (later → MQTT publish)
        print(json.dumps(packet, indent=2))

        time.sleep(2)  # simulate 2-second interval

if __name__ == "__main__":
    main()
