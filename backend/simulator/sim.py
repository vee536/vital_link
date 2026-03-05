import requests, time, random

URL = "http://127.0.0.1:8000/ingest/vitals"

def gen(amb):
    return {
        "ambulance_id": amb,
        "patient_id": "P-" + amb,
        "vitals": {
            "hr": random.randint(70,160),
            "spo2": random.randint(85,99),
            "bp_sys": random.randint(80,140),
            "bp_dia": random.randint(50,90),
            "rr": random.randint(12,30),
        }
    }

while True:
    for amb in ["AMB-101", "AMB-102", "AMB-103"]:
        requests.post(URL, json=gen(amb))
    time.sleep(1)
