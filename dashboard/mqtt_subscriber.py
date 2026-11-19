
import json
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "industrial/failure-detection/test"


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connected to MQTT broker successfully!")
        client.subscribe(TOPIC)
        print(f"Listening to topic: {TOPIC}")
        print("Waiting for ESP32 sensor readings...\n")
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))

        print("-" * 50)
        print("LIVE SENSOR DATA")
        print(f"Temperature : {data.get('temperature')} °C")
        print(f"Humidity    : {data.get('humidity')} %")
        print(f"Light       : {data.get('light')}")
        print(f"Acceleration: {data.get('ax')}, "
              f"{data.get('ay')}, {data.get('az')}")
        print(f"Gyroscope   : {data.get('gx')}, "
              f"{data.get('gy')}, {data.get('gz')}")

    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Received a message that is not valid JSON.")


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="failure_detection_python_subscriber"
)

client.on_connect = on_connect
client.on_message = on_message

print("Connecting to MQTT broker...")
client.connect(BROKER, PORT, 60)
client.loop_forever()
