import json
import ssl
import paho.mqtt.client as mqtt
import requests
import os

# MQTT topic
TOPIC = "vital-link/+/vitals"

# Backend API endpoint
BACKEND_INGEST = "http://127.0.0.1:8000/ingest/vitals"

# Path to certs
BASE_DIR = os.path.dirname(__file__)
SIM_DIR = os.path.join(BASE_DIR, "simulator")

CA_PATH = os.path.join(SIM_DIR, "AmazonRootCA1.pem")
CERT_PATH = os.path.join(SIM_DIR, "device-cert.pem.crt")
KEY_PATH = os.path.join(SIM_DIR, "device-private.pem.key")

# AWS endpoint
AWS_HOST = "a2dohm0tjgfpc3-ats.iot.us-east-1.amazonaws.com"

def on_connect(client, userdata, flags, rc):
    print("Connected to AWS IoT:", rc)
    client.subscribe(TOPIC, qos=1)

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print("Received:", payload)

    try:
        data = json.loads(payload)
        data["ambulance_id"] = "AMB-001"  # assign ambulance ID

        # send to FastAPI backend
        requests.post(BACKEND_INGEST, json=data)

    except Exception as e:
        print("Error:", e)

client = mqtt.Client()
client.tls_set(
    ca_certs=CA_PATH,
    certfile=CERT_PATH,
    keyfile=KEY_PATH,
    tls_version=ssl.PROTOCOL_TLSv1_2,
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(AWS_HOST, 8883)
client.loop_forever()
