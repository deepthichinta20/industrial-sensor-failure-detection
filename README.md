\# Industrial Sensor Failure Detection Using Multi-Variable Analytics



An IoT-based industrial monitoring system that detects abnormal sensor conditions using real-time data collected from an ESP32 and multiple sensors. The system uses MQTT communication, Python-based analytics, and a Flask dashboard to monitor industrial parameters and identify potential failures.



\## Project Overview



Industrial equipment can develop faults due to abnormal temperature, vibration, and environmental conditions. Detecting these abnormalities early can help reduce equipment downtime and improve maintenance efficiency.



This project collects sensor readings using an ESP32, transmits the data through MQTT, and processes it using a Python backend. A web-based dashboard displays sensor readings and system alerts.



\## Key Features



\- Real-time sensor data collection using ESP32.

\- Temperature and humidity monitoring using DHT11.

\- Vibration-related monitoring using an MPU6050-compatible sensor.

\- Light intensity monitoring using an LDR.

\- MQTT-based wireless communication.

\- Python-based multi-variable condition monitoring.

\- Flask web dashboard for sensor visualization.

\- Normal, warning, and critical condition detection.

\- CSV-based sensor data logging.

\- Alert history management.

\- SMS notifications using the CircuitDigest API.

\- OLED display and LED/buzzer indicators for local status indication.



\## System Architecture



```text

&#x20;      DHT11 + MPU Sensor + LDR

&#x20;                 |

&#x20;                 v

&#x20;               ESP32

&#x20;                 |

&#x20;                 v

&#x20;            MQTT Broker

&#x20;                 |

&#x20;                 v

&#x20;          Python Backend

&#x20;                 |

&#x20;         +-------+-------+

&#x20;         |       |       |

&#x20;         v       v       v

&#x20;      Failure   CSV    Alert

&#x20;     Detection Logging Management

&#x20;                 |

&#x20;                 v

&#x20;          SMS Notifications

&#x20;                 |

&#x20;                 v

&#x20;          Flask Dashboard

&#x20;                 |

&#x20;                 v

&#x20;         Real-Time Monitoring

```



\## Hardware Requirements



| Component | Purpose |

|---|---|

| ESP32 | Main microcontroller |

| DHT11 | Temperature and humidity sensing |

| MPU6050-compatible sensor | Motion and acceleration monitoring |

| LDR | Light intensity sensing |

| OLED Display | Local sensor information |

| LEDs | Visual status indication |

| Buzzer | Audio alert |

| Breadboard and jumper wires | Circuit connections |



\## Software and Technologies



\- \*\*Embedded Platform:\*\* Arduino IDE

\- \*\*Microcontroller:\*\* ESP32

\- \*\*Programming Languages:\*\* C/C++ and Python

\- \*\*Backend Framework:\*\* Flask

\- \*\*Communication Protocol:\*\* MQTT

\- \*\*MQTT Broker:\*\* HiveMQ Public Broker

\- \*\*Frontend:\*\* HTML, CSS, JavaScript

\- \*\*Data Storage:\*\* CSV and JSON

\- \*\*SMS Integration:\*\* CircuitDigest API



\## Project Structure



```text

industrial-sensor-failure-detection/

│

├── dashboard/

│   ├── app.py

│   ├── failure\_detector.py

│   ├── mqtt\_subscriber.py

│   └── templates/

│       └── index.html

│

├── sketch\_oct5a\_copy\_20261024232031/

│   └── sketch\_oct5a\_copy\_20261024232031.ino

│

└── .gitignore

```



\## Installation and Setup



\### 1. Clone the Repository



```bash

git clone https://github.com/deepthichinta20/industrial-sensor-failure-detection.git

```



\### 2. Navigate to the Project



```bash

cd industrial-sensor-failure-detection

```



\### 3. Install Python Dependencies



Install the required packages:



```bash

python -m pip install flask paho-mqtt requests python-dotenv

```



\### 4. Configure Environment Variables



Create a `.env` file inside the `dashboard` directory.



Add your own credentials:



```env

CIRCUITDIGEST\_API\_KEY=your\_api\_key

CIRCUITDIGEST\_MOBILE=your\_mobile\_number

```



\*\*Important:\*\* Never upload your actual `.env` file or API credentials to GitHub.



\### 5. Configure ESP32



\- Open the Arduino sketch in Arduino IDE.

\- Enter your Wi-Fi credentials.

\- Configure the MQTT broker and topic.

\- Select the correct ESP32 board and COM port.

\- Upload the program to the ESP32.



\### 6. Run the Flask Dashboard



Open a terminal inside the dashboard directory:



```bash

cd dashboard

python app.py

```



Open the dashboard in your browser:



\*\*Dashboard URL:\*\* `http://127.0.0.1:5000`



\## Failure Detection



The system evaluates sensor readings against configured thresholds to identify abnormal operating conditions.



| Parameter | Warning | Critical |

|---|---:|---:|

| Temperature | 40°C | 50°C |

| Vibration deviation | 0.30 g | 0.50 g |



The system also monitors device communication and can identify a device timeout after 12 seconds without receiving data.



\*Note: Thresholds are configurable in the backend source code.\*



\## Applications



\- Industrial equipment condition monitoring.

\- Early identification of abnormal operating conditions.

\- Predictive maintenance prototypes.

\- IoT-based industrial automation.

\- Remote equipment monitoring.



\## Limitations



\- The prototype uses a public MQTT broker and is intended for demonstration purposes.

\- The vibration measurement uses acceleration magnitude deviation as a simplified indicator; it is not a complete industrial vibration-frequency analysis.

\- Sensor accuracy and detection performance depend on sensor calibration and configured thresholds.

\- This prototype is not a certified industrial safety or protection system.



\## Future Improvements



\- Integration of machine learning for predictive maintenance.

\- Secure MQTT communication and authentication.

\- Cloud-based data storage.

\- Advanced vibration analysis.

\- Historical trend analysis and reporting.



\## Author



Developed as an IoT and Embedded Systems project.



\*\*Project:\*\* Industrial Sensor Failure Detection Using Multi-Variable Analytics



\*\*GitHub Repository:\*\*  

\[Industrial Sensor Failure Detection](https://github.com/deepthichinta20/industrial-sensor-failure-detection)



\---



\*This project demonstrates the integration of embedded systems, IoT communication, Python analytics, and web-based monitoring.\*

