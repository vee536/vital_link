import time
import random
import csv
import paho.mqtt.client as mqtt
from datetime import datetime

# MQTT setup
BROKER = "your-endpoint.amazonaws.com"
PORT = 8883
TOPIC = "vitals/data"

# Replace with correct paths to your certificates
CA_CERT = "AmazonRootCA1.pem"
CERTFILE = "certificate.pem.crt"
KEYFILE = "private.pem.key"

# Connect MQTT
client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT, certfile=CERTFILE, keyfile=KEYFILE)
client.connect(BROKER, PORT, 60)
client.loop_start()

# CSV setup
csv_file = "vitals_log.csv"
with open(csv_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "HeartRate", "SpO2", "BP_Systolic", "BP_Diastolic", "Alert"])

def generate_vitals():
    """Generate vitals, sometimes abnormal"""
    # Decide if abnormal
    abnormal = random.random() < 0.2   # 20% chance for abnormal values

    if abnormal:
        heart_rate = random.choice([random.randint(40, 55), random.randint(110, 140)])
        spo2 = random.choice([random.randint(80, 89)])
        bp_sys = random.choice([random.randint(150, 180)])
        bp_dia = random.choice([random.randint(95, 110)])
        alert = "ALERT"
    else:
        heart_rate = random.randint(60, 100)
        spo2 = random.randint(95, 100)
        bp_sys = random.randint(110, 130)
        bp_dia = random.randint(70, 85)
        alert = "OK"

    return heart_rate, spo2, bp_sys, bp_dia, alert

# Run simulation continuously
while True:
    hr, spo2, sys, dia, alert = generate_vitals()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "timestamp": timestamp,
        "heart_rate": hr,
        "spo2": spo2,
        "bp_systolic": sys,
        "bp_diastolic": dia,
        "alert": alert
    }

    # Publish to MQTT
    client.publish(TOPIC, str(data))

    # Write to CSV
    with open(csv_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, hr, spo2, sys, dia, alert])

    print(f"[{timestamp}] HR={hr}, SpO2={spo2}, BP={sys}/{dia}, Status={alert}")

    time.sleep(5)  # wait 5 sec before next reading
