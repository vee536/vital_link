import time
import random
import json
from datetime import datetime
# import paho.mqtt.client as mqtt   # Uncomment when setting up AWS IoT

# -------------------------------
# Patient Information
# -------------------------------
patient = {
    "name": input("Enter patient name: "),
    "age": int(input("Enter patient age: "))
}

# -------------------------------
# Temporary JSON Buffer
# -------------------------------
buffer_file = "vitals_buffer.json"

def save_to_buffer(data):
    try:
        with open(buffer_file, "a") as f:  # append mode
            f.write(json.dumps(data) + "\n")
    except Exception as e:
        print(f"Error writing to buffer: {e}")

# -------------------------------
# Alert System
# -------------------------------
def check_alerts(vitals):
    alerts = []
    if vitals["spo2"] < 92:
        alerts.append("⚠️ Low SpO₂ detected!")
    if vitals["heart_rate"] < 60 or vitals["heart_rate"] > 100:
        alerts.append("⚠️ Abnormal heart rate!")
    if vitals["bp_sys"] > 140 or vitals["bp_dia"] > 90:
        alerts.append("⚠️ High blood pressure!")
    return alerts

# -------------------------------
# MQTT Setup (placeholder for AWS IoT)
# -------------------------------
"""
mqtt_client = mqtt.Client()
mqtt_client.tls_set("AmazonRootCA1.pem", certfile="deviceCert.crt", keyfile="privateKey.key")
mqtt_client.connect("YOUR_ENDPOINT.iot.region.amazonaws.com", 8883, 60)
"""

# -------------------------------
# Main Loop
# -------------------------------
print("\n--- Vital Signs Monitoring Started ---\n")
while True:
    vitals = {
        "timestamp": datetime.utcnow().isoformat(),
        "patient": patient,
        "heart_rate": random.randint(55, 110),   # bpm
        "spo2": random.randint(88, 99),          # %
        "bp_sys": random.randint(100, 160),      # mmHg
        "bp_dia": random.randint(60, 100)        # mmHg
    }

    # Check alerts
    alerts = check_alerts(vitals)
    vitals["alerts"] = alerts

    # Print to console
    print(f"HR: {vitals['heart_rate']} bpm | SpO₂: {vitals['spo2']}% | "
          f"BP: {vitals['bp_sys']}/{vitals['bp_dia']} mmHg | Alerts: {alerts}")

    # Save to JSON buffer
    save_to_buffer(vitals)

    # MQTT publish (when AWS IoT ready)
    """
    mqtt_client.publish("ambulance/vitals", json.dumps(vitals))
    """

    time.sleep(2)  # update every 2 sec
