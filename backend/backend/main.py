from fastapi import FastAPI, WebSocket
import asyncio
from rule_engine import check_rules
from ai_engine import ai_risk
from fastapi import Body

app = FastAPI()

# temporary storage (replace with DB later)
latest_vitals = {}
alerts = {}
ai_risk_store = {}

@app.post("/ingest/vitals")
def ingest(vitals = Body(...)):
    amb = vitals["ambulance_id"]
    latest_vitals[amb] = vitals

    # rules engine
    rule_alerts = check_rules(vitals)
    if rule_alerts:
        alerts.setdefault(amb, []).extend(rule_alerts)

    # AI risk engine (dummy)
    ai_risk_store[amb] = ai_risk(vitals)

    return {"status": "ok"}

@app.get("/ambulances")
def get_ambulances():
    return list(latest_vitals.keys())

@app.get("/ambulance/{amb_id}/latest")
def get_latest(amb_id):
    data = latest_vitals.get(amb_id, {})
    risk = ai_risk_store.get(amb_id, {})
    return {"vitals": data, "ai": risk}

@app.get("/ambulance/{amb_id}/alerts")
def get_alerts(amb_id):
    return alerts.get(amb_id, [])

@app.websocket("/live/{amb_id}")
async def websocket_endpoint(ws: WebSocket, amb_id: str):
    await ws.accept()
    while True:
        if amb_id in latest_vitals:
            await ws.send_json(latest_vitals[amb_id])
        await asyncio.sleep(1)
