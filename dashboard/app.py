
import re
import queue
import requests
from dotenv import load_dotenv

import csv
import json
import math
import os
import time

from datetime import datetime
from threading import Lock, Thread

import paho.mqtt.client as mqtt

from flask import Flask, jsonify, render_template


app = Flask(__name__)


# ==================================================
# 1. MQTT SETTINGS
# ==================================================

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "industrial/failure-detection/test"


# ==================================================
# 2. DETECTION THRESHOLDS
# ==================================================

TEMP_WARNING_C = 40.0
TEMP_CRITICAL_C = 50.0

VIBRATION_WARNING_G = 0.30
VIBRATION_CRITICAL_G = 0.50

DEVICE_TIMEOUT_SECONDS = 12


# ==================================================
# 3. FILE SETTINGS
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

CSV_FILE = os.path.join(BASE_DIR, "sensor_readings.csv")
ALERT_FILE = os.path.join(BASE_DIR, "alert_history.json")

CSV_COLUMNS = [
    "timestamp", "temperature", "humidity", "light",
    "ax", "ay", "az", "gx", "gy", "gz",
    "acceleration", "vibration_variation",
    "status", "alerts"
]


# ==================================================
# 4. CIRCUITDIGEST SMS SETTINGS
# ==================================================

CD_API_KEY = os.getenv("CIRCUITDIGEST_API_KEY", "").strip()
CD_MOBILE = os.getenv("CIRCUITDIGEST_MOBILE", "").strip()

CD_TEMPLATE_ID = "101"

SMS_API_URL = (
    "https://www.circuitdigest.cloud/api/v1/send_sms?ID="
    + CD_TEMPLATE_ID
)

SMS_COOLDOWN_SECONDS = 60

sms_queue = queue.Queue(maxsize=20)

last_sms_sent_epoch = 0


# ==================================================
# 5. THREAD LOCKS
# ==================================================

data_lock = Lock()
csv_lock = Lock()


# ==================================================
# 6. GLOBAL VARIABLES
# ==================================================

active_alerts = set()
alert_history = []

last_seen_epoch = None

latest_data = {

    "temperature": None,
    "humidity": None,
    "light": None,

    "ax": None,
    "ay": None,
    "az": None,

    "gx": None,
    "gy": None,
    "gz": None,

    "acceleration": None,
    "vibration_variation": None,

    "dht_valid": None,
    "mpu_valid": None,

    "sensor_health": {
        "dht11": "WAITING",
        "mpu": "WAITING"
    },

    "uptime_ms": None,

    "device_online": False,
    "last_seen": None,

    "status": "WAITING",
    "alerts": [],

    "alert_history": [],

    "sms_status": "NOT SENT",

    "updated_at": None
}


# ==================================================
# 7. CSV INITIALIZATION
# ==================================================

def initialize_csv():

    with csv_lock:

        if (
            not os.path.exists(CSV_FILE)
            or os.path.getsize(CSV_FILE) == 0
        ):

            with open(
                CSV_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=CSV_COLUMNS
                )

                writer.writeheader()

    print("CSV logging file:", CSV_FILE)


def save_reading(row):

    try:

        with csv_lock:

            with open(
                CSV_FILE,
                "a",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=CSV_COLUMNS
                )

                writer.writerow(row)
                file.flush()

    except (OSError, ValueError) as error:

        print("CSV logging error:", error)


# ==================================================
# 8. SMS FUNCTIONS
# ==================================================

def update_sms_status(status):

    with data_lock:
        latest_data["sms_status"] = status


def enqueue_sms(alerts):

    if not CD_API_KEY or not CD_MOBILE:

        print("SMS not configured. Check your .env file.")
        return

    machine_name = "Industrial Machine 01"

    combined_alert = " AND ".join(alerts)

    # Keep the message variable short and safe.
    alert_message = re.sub(
        r"[^A-Za-z0-9 ]",
        "",
        combined_alert
    )

    alert_message = " ".join(
        alert_message.split()
    )[:30]

    try:

        sms_queue.put_nowait(
            (machine_name, alert_message)
        )

        print("SMS added to queue:", alert_message)

    except queue.Full:

        print("SMS queue full. Alert not queued.")


def sms_worker():

    global last_sms_sent_epoch

    if not CD_API_KEY or not CD_MOBILE:

        print("CircuitDigest SMS credentials not configured.")

        update_sms_status("NOT CONFIGURED")

    else:

        print("CircuitDigest SMS worker started.")

    headers = {

        "Authorization": CD_API_KEY,
        "Content-Type": "application/json"

    }

    while True:

        machine_name, alert_message = sms_queue.get()

        try:

            # Enforce cooldown without discarding queued alerts.
            elapsed = time.time() - last_sms_sent_epoch

            remaining = SMS_COOLDOWN_SECONDS - elapsed

            if remaining > 0:

                print(
                    f"SMS cooldown: waiting {remaining:.1f} seconds"
                )

                time.sleep(remaining)

            payload = {

                "mobiles": CD_MOBILE,
                "var1": machine_name,
                "var2": alert_message

            }

            print("Sending CircuitDigest SMS:", alert_message)

            response = requests.post(
                SMS_API_URL,
                headers=headers,
                json=payload,
                timeout=15
            )

            print("CircuitDigest response:", response.text)

            if response.status_code == 200:

                last_sms_sent_epoch = time.time()

                update_sms_status("SENT")

                print("SMS sent successfully.")

            else:

                update_sms_status("FAILED")

                print(
                    "SMS failed:",
                    response.status_code,
                    response.text
                )

        except requests.RequestException as error:

            update_sms_status("FAILED")

            print("SMS connection error:", error)

        except Exception as error:

            update_sms_status("FAILED")

            print("Unexpected SMS error:", error)

        finally:

            sms_queue.task_done()


# ==================================================
# 9. ALERT HISTORY
# ==================================================

def initialize_alert_history():

    global alert_history, active_alerts

    if not os.path.exists(ALERT_FILE):
        return

    try:

        with open(
            ALERT_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            saved_data = json.load(file)

        alert_history = saved_data.get(
            "history", []
        )[-100:]

        active_alerts = set(
            saved_data.get("active_alerts", [])
        )

        print(
            "Previous alert history loaded:",
            len(alert_history)
        )

    except (
        OSError,
        json.JSONDecodeError,
        TypeError
    ) as error:

        print("Could not load alert history:", error)


def save_alert_history():

    temporary_file = ALERT_FILE + ".tmp"

    try:

        saved_data = {

            "history": alert_history[-100:],

            "active_alerts": list(active_alerts)

        }

        with open(
            temporary_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                saved_data,
                file,
                indent=4
            )

        os.replace(
            temporary_file,
            ALERT_FILE
        )

    except (OSError, TypeError) as error:

        print("Alert history save error:", error)


def update_alert_history(alerts, status, timestamp):

    global active_alerts, alert_history

    current_alerts = set(alerts)

    new_alerts = current_alerts - active_alerts

    recovered_alerts = active_alerts - current_alerts

    # Record new alerts.

    for alert in sorted(new_alerts):

        severity = (
            "CRITICAL"
            if alert.startswith("CRITICAL")
            else "WARNING"
        )

        if "SENSOR FAULT" in alert:
            severity = "FAULT"

        if alert == "DEVICE OFFLINE":
            severity = "FAULT"

        event = {

            "alert": alert,
            "severity": severity,
            "status": status,
            "event_type": "ALERT",
            "timestamp": timestamp

        }

        alert_history.append(event)

        print("NEW ALERT:", alert)

    # Record recovered alerts.

    for alert in sorted(recovered_alerts):

        event = {

            "alert": alert,
            "severity": "INFO",
            "status": status,
            "event_type": "RECOVERY",
            "timestamp": timestamp

        }

        alert_history.append(event)

        print("RECOVERED:", alert)

    alert_history = alert_history[-100:]

    active_alerts = current_alerts

    # Send SMS only for newly activated alerts.

    if new_alerts:

        enqueue_sms(sorted(new_alerts))

    if new_alerts or recovered_alerts:

        save_alert_history()


# ==================================================
# 10. DATA VALIDATION HELPERS
# ==================================================

def safe_float(value, default=None):

    try:

        number = float(value)

        if not math.isfinite(number):
            return default

        return number

    except (ValueError, TypeError):

        return default


def safe_bool(value, default=False):

    if isinstance(value, bool):
        return value

    if isinstance(value, str):

        return value.strip().lower() in (
            "true", "1", "yes"
        )

    if isinstance(value, (int, float)):

        return value == 1

    return default


# ==================================================
# 11. VIBRATION CALCULATION
# ==================================================

def calculate_vibration(acceleration):

    return abs(acceleration - 1.0)


# ==================================================
# 12. FAILURE DETECTION
# ==================================================

def detect_failure(
    temperature,
    vibration,
    dht_valid,
    mpu_valid
):

    alerts = []

    # Temperature detection.

    if dht_valid:

        if temperature >= TEMP_CRITICAL_C:

            alerts.append("CRITICAL TEMPERATURE")

        elif temperature >= TEMP_WARNING_C:

            alerts.append("HIGH TEMPERATURE")

    # Vibration detection.

    if mpu_valid and vibration is not None:

        if vibration >= VIBRATION_CRITICAL_G:

            alerts.append("CRITICAL VIBRATION")

        elif vibration >= VIBRATION_WARNING_G:

            alerts.append("UNUSUAL VIBRATION")

    # Sensor health.

    if not dht_valid:

        alerts.append("DHT SENSOR FAULT")

    if not mpu_valid:

        alerts.append("MPU SENSOR FAULT")

    # Overall status.

    if (
        "CRITICAL TEMPERATURE" in alerts
        or "CRITICAL VIBRATION" in alerts
    ):

        status = "CRITICAL"

    elif (
        "HIGH TEMPERATURE" in alerts
        or "UNUSUAL VIBRATION" in alerts
    ):

        status = "WARNING"

    elif not dht_valid or not mpu_valid:

        status = "FAULT"

    else:

        status = "NORMAL"

    return status, alerts


# ==================================================
# 13. MQTT CONNECTION CALLBACK
# ==================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties=None
):

    if reason_code == 0:

        print("Dashboard connected to MQTT!")

        client.subscribe(TOPIC)

        print("Subscribed to:", TOPIC)

    else:

        print("MQTT connection failed:", reason_code)


# ==================================================
# 14. MQTT MESSAGE CALLBACK
# ==================================================

def on_message(client, userdata, message):

    global last_seen_epoch

    try:

        data = json.loads(
            message.payload.decode("utf-8")
        )

        # Read sensor values.

        temperature = safe_float(
            data.get("temperature")
        )

        humidity = safe_float(
            data.get("humidity")
        )

        light = safe_float(
            data.get("light")
        )

        ax = safe_float(data.get("ax"))
        ay = safe_float(data.get("ay"))
        az = safe_float(data.get("az"))

        gx = safe_float(data.get("gx"))
        gy = safe_float(data.get("gy"))
        gz = safe_float(data.get("gz"))

        # Validate DHT11.

        inferred_dht_valid = (

            temperature is not None
            and humidity is not None
            and 0 <= temperature <= 50
            and 0 <= humidity <= 100

        )

        dht_valid = safe_bool(
            data.get("dht_valid"),
            inferred_dht_valid
        )

        dht_valid = (
            dht_valid
            and inferred_dht_valid
        )

        # Validate MPU.

        inferred_mpu_valid = all(

            value is not None

            for value in [ax, ay, az, gx, gy, gz]

        )

        mpu_valid = safe_bool(
            data.get("mpu_valid"),
            inferred_mpu_valid
        )

        mpu_valid = (
            mpu_valid
            and inferred_mpu_valid
        )

        # Calculate acceleration and vibration.

        acceleration = None
        vibration = None

        if mpu_valid:

            acceleration = math.sqrt(
                ax ** 2 +
                ay ** 2 +
                az ** 2
            )

            vibration = calculate_vibration(
                acceleration
            )

        # Detect failure.

        status, alerts = detect_failure(
            temperature,
            vibration,
            dht_valid,
            mpu_valid
        )

        # Timestamp.

        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        uptime_ms = data.get("uptime_ms")

        try:

            uptime_ms = int(uptime_ms)

            if uptime_ms < 0:
                uptime_ms = None

        except (ValueError, TypeError):

            uptime_ms = None

        now_epoch = time.time()

        # Update dashboard data.

        with data_lock:

            last_seen_epoch = now_epoch

            update_alert_history(
                alerts,
                status,
                timestamp
            )

            reading = {

                "temperature": temperature,
                "humidity": humidity,
                "light": light,

                "ax": ax,
                "ay": ay,
                "az": az,

                "gx": gx,
                "gy": gy,
                "gz": gz,

                "acceleration": acceleration,

                "vibration_variation": vibration,

                "dht_valid": dht_valid,
                "mpu_valid": mpu_valid,

                "sensor_health": {

                    "dht11": (
                        "OK" if dht_valid else "FAULT"
                    ),

                    "mpu": (
                        "OK" if mpu_valid else "FAULT"
                    )

                },

                "uptime_ms": uptime_ms,

                "device_online": True,
                "last_seen": timestamp,

                "status": status,
                "alerts": alerts,

                "alert_history": list(
                    reversed(alert_history)
                ),

                "updated_at": timestamp

            }

            latest_data.update(reading)

        # Save CSV reading.

        csv_row = {

            "timestamp": timestamp,

            "temperature": temperature,
            "humidity": humidity,
            "light": light,

            "ax": ax,
            "ay": ay,
            "az": az,

            "gx": gx,
            "gy": gy,
            "gz": gz,

            "acceleration": acceleration,
            "vibration_variation": vibration,

            "status": status,
            "alerts": "; ".join(alerts)

        }

        save_reading(csv_row)

        # Server output.

        print(

            f"Temperature={temperature} C | "
            f"Humidity={humidity} % | "
            f"Vibration={vibration} g | "
            f"DHT={'OK' if dht_valid else 'FAULT'} | "
            f"MPU={'OK' if mpu_valid else 'FAULT'} | "
            f"Status={status} | "
            f"Alerts={alerts}"

        )

    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ) as error:

        print("Invalid sensor message:", error)


# ==================================================
# 15. MQTT LISTENER
# ==================================================

def start_mqtt():

    client = mqtt.Client(

        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,

        client_id="industrial_dashboard_" + str(int(time.time()))

    )

    client.on_connect = on_connect
    client.on_message = on_message

    try:

        client.connect(
            BROKER,
            PORT,
            60
        )

        client.loop_forever()

    except Exception as error:

        print("MQTT listener error:", error)


# ==================================================
# 16. DEVICE ONLINE CHECK
# ==================================================

def get_device_online_status():

    if last_seen_epoch is None:
        return False

    return (

        time.time() - last_seen_epoch
        <= DEVICE_TIMEOUT_SECONDS

    )


# ==================================================
# 17. DASHBOARD ROUTES
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")


@app.route("/api/data")
def get_data():

    with data_lock:

        response = dict(latest_data)

        response["sensor_health"] = dict(
            latest_data["sensor_health"]
        )

        response["alert_history"] = list(
            reversed(alert_history)
        )

        online = get_device_online_status()

        response["device_online"] = online

        if last_seen_epoch is not None:

            response["seconds_since_last_message"] = round(

                time.time() - last_seen_epoch,
                1

            )

        else:

            response["seconds_since_last_message"] = None

        # Detect the transition to OFFLINE only once.

        if last_seen_epoch is not None and not online:

            timestamp = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )

            if "DEVICE OFFLINE" not in active_alerts:

                active_alerts.add("DEVICE OFFLINE")

                event = {

                    "alert": "DEVICE OFFLINE",
                    "severity": "FAULT",
                    "status": "OFFLINE",
                    "event_type": "ALERT",
                    "timestamp": timestamp

                }

                alert_history.append(event)

                alert_history[:] = alert_history[-100:]

                save_alert_history()

                enqueue_sms(["DEVICE OFFLINE"])

                print("NEW ALERT: DEVICE OFFLINE")

            response["status"] = "OFFLINE"

            response["alerts"] = ["DEVICE OFFLINE"]

            response["alert_history"] = list(
                reversed(alert_history)
            )

        elif last_seen_epoch is None:

            response["status"] = "WAITING"

            response["alerts"] = []

    return jsonify(response)


@app.route("/api/alerts")
def get_alerts():

    with data_lock:

        return jsonify(
            list(reversed(alert_history))
        )


# ==================================================
# 18. APPLICATION START
# ==================================================

if __name__ == "__main__":

    initialize_csv()

    initialize_alert_history()

    # Start SMS background worker.

    sms_thread = Thread(
        target=sms_worker,
        daemon=True
    )

    sms_thread.start()

    # Start MQTT listener.

    mqtt_thread = Thread(
        target=start_mqtt,
        daemon=True
    )

    mqtt_thread.start()

    print("--------------------------------------")
    print("INDUSTRIAL SENSOR FAILURE DETECTION")
    print("--------------------------------------")

    print("Dashboard: http://127.0.0.1:5000")
    print("MQTT Topic:", TOPIC)

    if CD_API_KEY and CD_MOBILE:

        print("CircuitDigest SMS: CONFIGURED")

    else:

        print("CircuitDigest SMS: NOT CONFIGURED")

    app.run(

        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True

    )
