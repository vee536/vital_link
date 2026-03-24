import json
import time
import random
import ssl
import sys
import paho.mqtt.client as mqtt

# ---------------------------- Ambulance ID from CLI ----------------------------
if len(sys.argv) < 2:
    print("❌ Usage: python vitals_mqtt_client.py <ambulance_id>")
    print("   Example: python vitals_mqtt_client.py A1")
    sys.exit(1)

ambulance_id = sys.argv[1].strip()
print(f"🚑 Starting simulator for Ambulance: {ambulance_id}")

# AWS IoT Core endpoint
AWS_ENDPOINT = "aj3jbl23441fa-ats.iot.eu-north-1.amazonaws.com"
AWS_PORT = 8883

# File paths for certs/keys
CA_PATH = "AmazonRootCA1.pem"
CERT_PATH = "device-cert.pem.crt"
KEY_PATH = "device-private.pem.key"

# MQTT topic — unique per ambulance
TOPIC = f"vital-link/{ambulance_id}/vitals"

# MQTT client setup — unique client_id to avoid broker collisions
client = mqtt.Client(client_id=f"vitallink-{ambulance_id}-{int(time.time())}")

# Configure TLS/SSL
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
        print(f"✅ [{ambulance_id}] Connected to AWS IoT Core")
    else:
        print(f"❌ [{ambulance_id}] Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    global connected_flag
    connected_flag = False
    print(f"⚠️ [{ambulance_id}] Disconnected from AWS IoT Core. Retrying...")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    print(f"[{ambulance_id}] Connecting to AWS IoT Core...")
    client.connect(AWS_ENDPOINT, AWS_PORT, keepalive=60)
    client.loop_start()
except Exception as e:
    print(f"❌ [{ambulance_id}] Initial connection error: {e}")

def simulate_vitals():
    """Simulate random vital signs with varied alerts for demo"""
    hr   = random.choice([75, 95, 115, 130])
    spo2 = random.choice([95, 92, 88, 85])
    temp = round(random.choice([36.5, 37.2, 38.5, 39.0]), 1)
    bp_sys = random.randint(110, 140)
    bp_dia = random.randint(70, 90)

    alerts = []
    if spo2 < 90:   alerts.append("Low Oxygen Level")
    if hr > 110:    alerts.append("Tachycardia (High HR)")
    if temp > 38.0: alerts.append("Fever Detected")

    return {
        "ambulance_id": ambulance_id,           # ✅ included in every payload
        "patient": {
            "name": f"Demo Patient ({ambulance_id})",
            "age": random.randint(20, 70),
        },
        "vitals": {
            "heart_rate": hr,
            "spo2": spo2,
            "temperature": temp,
            "bp_sys": bp_sys,
            "bp_dia": bp_dia,
        },
        "alerts": alerts,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

# Publish loop
try:
    while True:
        if connected_flag:
            data = simulate_vitals()
            payload = json.dumps(data)
            try:
                client.publish(TOPIC, payload, qos=1)
                print(f"📡 [{ambulance_id}] Published: {payload}")
            except Exception as e:
                print(f"❌ [{ambulance_id}] Publish error: {e}")
        else:
            print(f"⏳ [{ambulance_id}] Waiting for connection...")
        time.sleep(5)
except KeyboardInterrupt:
    print(f"\n[{ambulance_id}] Stopping simulation...")
    client.loop_stop()
    client.disconnect()
