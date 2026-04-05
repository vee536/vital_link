import json
import boto3
import urllib3
from collections import deque

http = urllib3.PoolManager()
COLAB_URL = "https://nonimitable-beatriz-editorially.ngrok-free.dev"

connections = set()

# Rolling buffer per patient — persists across warm Lambda invocations
patient_buffers = {}
WINDOW_SIZE = 200

def lambda_handler(event, context):
    print("EVENT RECEIVED:")
    print(json.dumps(event, indent=2))

    # Handle WebSocket events
    if "requestContext" in event:
        route = event["requestContext"]["routeKey"]
        connection_id = event["requestContext"]["connectionId"]

        if route == "$connect":
            connections.add(connection_id)
            print("Client connected:", connection_id)
            return {"statusCode": 200}

        elif route == "$disconnect":
            connections.discard(connection_id)
            print("Client disconnected:", connection_id)
            return {"statusCode": 200}

    # Handle IoT Core message
    else:
        print("IoT message received")

        vitals = event.get("vitals", {})
        patient_id = event.get("patient", {}).get("name", "unknown")

        # Initialize buffer for new patient
        if patient_id not in patient_buffers:
            patient_buffers[patient_id] = deque(maxlen=WINDOW_SIZE)

        # Add current reading to rolling buffer
        patient_buffers[patient_id].append([
            vitals.get("heart_rate", 75),
            vitals.get("spo2", 98),
            vitals.get("bp_sys", 120),
            vitals.get("bp_dia", 80),
            vitals.get("temperature", 37.0),
        ])

        buf = patient_buffers[patient_id]
        print(f"Buffer size for {patient_id}: {len(buf)}")

        # Pad with first reading if buffer not full yet
        first_reading = list(buf)[0]
        window = list(buf)
        while len(window) < WINDOW_SIZE:
            window.insert(0, first_reading)

        # Call Colab ML server
        ai_result = {}
        try:
            response = http.request(
                'POST',
                f"{COLAB_URL}/predict",
                body=json.dumps({"window": window}),
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            ai_result = json.loads(response.data.decode('utf-8'))
            print("AI result:", ai_result)
        except Exception as e:
            print("ML inference error:", e)
            ai_result = {"condition": "Unknown", "severity": "unknown", "error": str(e)}

        # Enrich payload with AI
        enriched_event = {
            **event,
            "ai": {
                "condition":       ai_result.get("condition", "Unknown"),
                "severity":        ai_result.get("severity", "Unknown"),
                "confidence":      ai_result.get("confidence", 0),
                "actions":         ai_result.get("actions", []),        # ✅ add this
                "icu_probability": ai_result.get("icu_probability", 0), # ✅ add this
            }
        }

        # Broadcast to WebSocket clients
        apigateway = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url="https://018nlv643l.execute-api.eu-north-1.amazonaws.com/production"
        )

        for connection_id in list(connections):
            try:
                apigateway.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps(enriched_event)
                )
                print("Sent data to:", connection_id)
            except Exception as e:
                print("Error sending to:", connection_id, e)
                connections.discard(connection_id)

        return {"statusCode": 200}