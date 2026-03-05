def check_rules(v):
    data = v["vitals"]
    alerts = []

    if data["spo2"] < 90:
        alerts.append("Critical: SpO2 < 90")

    if data["hr"] > 150:
        alerts.append("Critical: HR > 150")

    if data["bp_sys"] < 90:
        alerts.append("Warning: BP Low")

    return alerts if alerts else None
