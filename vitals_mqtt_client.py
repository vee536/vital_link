import json
import time
import random
import ssl
import paho.mqtt.client as mqtt

# AWS IoT Core endpoint
AWS_ENDPOINT = "a2dohm0tjgfpc3-ats.iot.us-east-1.amazonaws.com"
AWS_PORT = 8883

# File paths for certs/keys
CA_PATH = "AmazonRootCA1.pem"
CERT_PATH = "device-cert.pem.crt"
KEY_PATH = "device-private.pem.key"

# MQTT topic
TOPIC = "vital-link/ambulance1/vitals"

# MQTT client setup
client = mqtt.Client()

# Configure TLS/SSL
client.tls_set(
    ca_certs=CA_PATH,
    certfile=CERT_PATH,
    keyfile=KEY_PATH,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

# Flags for connection status
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
    print("⚠️ Disconnected from AWS IoT Core. Retrying...")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Attempt initial connection
try:
    print("Connecting to AWS IoT Core...")
    client.connect(AWS_ENDPOINT, AWS_PORT, keepalive=60)
    client.loop_start()
except Exception as e:
    print(f"❌ Initial connection error: {e}")

def simulate_vitals():
    """Simulate random vital signs with varied alerts for demo"""
    
    vitals = {
        "patient_name": "Demo Patient",
        "patient_age": random.randint(20, 70),
        # Randomly pick normal or abnormal values for demo
        "heart_rate": random.choice([75, 95, 115, 130]),  # normal and high
        "spo2": random.choice([95, 92, 88, 85]),          # normal and low
        "temperature": round(random.choice([36.5, 37.2, 38.5, 39.0]), 1),
        "blood_pressure": f"{random.randint(110, 140)}/{random.randint(70, 90)}"
    }

    alerts = []
    if vitals["spo2"] < 90:
        alerts.append("ALERT: Low SpO2!")
    if vitals["heart_rate"] > 110:
        alerts.append("ALERT: High Heart Rate!")
    if vitals["temperature"] > 38.0:
        alerts.append("ALERT: High Temperature!")

    vitals["alerts"] = alerts
    return vitals

# Publish loop
try:
    while True:
        if connected_flag:
            data = simulate_vitals()
            payload = json.dumps(data)
            try:
                client.publish(TOPIC, payload, qos=1)
                print(f"Published: {payload}")
            except Exception as e:
                print(f"❌ Publish error: {e}")
        else:
            print("⏳ Waiting for connection...")
        time.sleep(5)
except KeyboardInterrupt:
    print("\nStopping simulation...")
    client.loop_stop()
    client.disconnect()
