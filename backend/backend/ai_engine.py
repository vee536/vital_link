def ai_risk(v):
    hr = v["vitals"]["hr"]
    spo2 = v["vitals"]["spo2"]

    if spo2 < 92 and hr > 120:
        return {"risk": "High", "reason": "Possible respiratory distress"}
    if spo2 < 95:
        return {"risk": "Medium", "reason": "Monitor oxygen levels"}
    return {"risk": "Low", "reason": "Stable"}
