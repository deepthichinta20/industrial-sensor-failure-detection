
import json
import math
import time
from collections import deque

import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "industrial/failure-detection/test"

TEMP_WARNING_C = 40.0
VIBRATION_WARNING_G = 1.50
WINDOW_SIZE = 10

acceleration_history = deque(maxlen=WINDOW_SIZE)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connected to MQTT broker!")
        client.subscribe(TOPIC)
        print("Monitoring sensor data...\n")
    else:
        print("Connection failed:", reason_code)


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))

        temperature = float(data["temperature"])
        ax = float(data["ax"])
        ay = float(data["ay"])
        az = float(data["az"])

        acceleration = math.sqrt(ax**2 + ay**2 + az**2)
        acceleration_history.append(acceleration)

        alerts = []
        variation = None

        if temperature >= TEMP_WARNING_C:
            alerts.append("HIGH TEMPERATURE")

        if len(acceleration_history) == WINDOW_SIZE:
            mean = sum(acceleration_history) / WINDOW_SIZE
            variation = math.sqrt(
                sum((x - mean) ** 2 for x in acceleration_history)
                / WINDOW_SIZE
            )

            if variation >= VIBRATION_WARNING_G:
                alerts.append("UNUSUAL ACCELERATION VARIATION")

        if len(alerts) >= 2:
            status = "CRITICAL - MULTIPLE ANOMALIES"
        elif alerts:
            status = "WARNING"
        else:
            status = "NORMAL"

        print("-" * 45)
        print(f"Temperature: {temperature:.2f} C")
        print(f"Acceleration magnitude: {acceleration:.3f} g")

        if variation is None:
            print(f"Collecting samples: {len(acceleration_history)}/{WINDOW_SIZE}")
        else:
            print(f"Acceleration variation: {variation:.4f} g")

        print("Status:", status)

        for alert in alerts:
            print("Alert:", alert)

        print("Time:", time.strftime("%H:%M:%S"))

    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print("Could not process message:", error)


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="failure_detector_python"
)

client.on_connect = on_connect
client.on_message = on_message

print("Starting failure detector...")
client.connect(BROKER, PORT, 60)
client.loop_forever()
