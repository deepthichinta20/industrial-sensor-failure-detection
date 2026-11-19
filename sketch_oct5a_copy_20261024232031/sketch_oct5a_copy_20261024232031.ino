
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

// ==================================================
// 1. WIFI SETTINGS
// ==================================================

const char* WIFI_SSID = "Chinta";
const char* WIFI_PASSWORD = "Rainbow@123";

// Enter your actual Wi-Fi password locally.
// Do not share it publicly.

// ==================================================
// 2. MQTT SETTINGS
// ==================================================

const char* MQTT_BROKER = "broker.hivemq.com";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "industrial/failure-detection/test";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// ==================================================
// 3. SENSOR PINS
// ==================================================

#define DHT_PIN 4
#define DHT_TYPE DHT11

#define LDR_PIN 35

#define SDA_PIN 21
#define SCL_PIN 22

#define MPU_ADDRESS 0x68

// ==================================================
// 4. LED AND BUZZER PINS
// ==================================================

#define GREEN_LED_PIN 25
#define YELLOW_LED_PIN 26
#define RED_LED_PIN 27
#define BUZZER_PIN 18

// ==================================================
// 5. OLED SETTINGS
// ==================================================

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDRESS 0x3C
#define OLED_RESET -1

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);

DHT dht(DHT_PIN, DHT_TYPE);

// ==================================================
// 6. WARNING THRESHOLDS
// ==================================================

const float TEMP_WARNING_C = 40.0;
const float TEMP_CRITICAL_C = 50.0;

const float VIBRATION_WARNING_G = 0.30;
const float VIBRATION_CRITICAL_G = 0.50;

// ==================================================
// 7. SENSOR VARIABLES
// ==================================================

float temperature = NAN;
float humidity = NAN;

int lightValue = 0;

float ax = 0.0;
float ay = 0.0;
float az = 0.0;

float gx = 0.0;
float gy = 0.0;
float gz = 0.0;

float accelerationMagnitude = 0.0;
float vibration = 0.0;

// Sensor health
bool dhtValid = false;
bool mpuValid = false;
bool mpuInitialized = false;

// ==================================================
// 8. SYSTEM STATUS
// ==================================================

enum SystemStatus {
  NORMAL,
  WARNING,
  CRITICAL,
  FAULT
};

SystemStatus currentStatus = NORMAL;

unsigned long lastSensorRead = 0;
unsigned long systemStartTime = 0;

const unsigned long SENSOR_INTERVAL = 3000;

// ==================================================
// 9. MPU REGISTER FUNCTIONS
// ==================================================

void writeMPURegister(byte reg, byte value) {

  Wire.beginTransmission(MPU_ADDRESS);
  Wire.write(reg);
  Wire.write(value);

  byte result = Wire.endTransmission();

  if (result != 0) {
    Serial.println("MPU register write failed.");
  }
}

// Read MPU register safely.
// Returns false if I2C communication fails.

bool readMPUWord(byte reg, int16_t &value) {

  Wire.beginTransmission(MPU_ADDRESS);
  Wire.write(reg);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(MPU_ADDRESS, (uint8_t)2) != 2) {
    return false;
  }

  uint8_t highByte = Wire.read();
  uint8_t lowByte = Wire.read();

  value = (int16_t)(
    ((uint16_t)highByte << 8) | lowByte
  );

  return true;
}

// ==================================================
// 10. MPU INITIALIZATION
// ==================================================

bool initializeMPU() {

  Wire.beginTransmission(MPU_ADDRESS);
  Wire.write(0x75);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(MPU_ADDRESS, (uint8_t)1) != 1) {
    return false;
  }

  byte identity = Wire.read();

  Serial.print("MPU WHO_AM_I: 0x");
  Serial.println(identity, HEX);

  if (identity == 0x00 || identity == 0xFF) {
    return false;
  }

  // Wake up MPU
  writeMPURegister(0x6B, 0x00);

  // Accelerometer range: +/- 2g
  writeMPURegister(0x1C, 0x00);

  // Gyroscope range: +/- 250 degrees/sec
  writeMPURegister(0x1B, 0x00);

  delay(100);

  return true;
}

// ==================================================
// 11. READ MPU SENSOR
// ==================================================

bool readMPU() {

  int16_t rawAX, rawAY, rawAZ;
  int16_t rawGX, rawGY, rawGZ;

  if (!mpuInitialized) {
    mpuValid = false;
    return false;
  }

  // Check all six register readings

  if (
    !readMPUWord(0x3B, rawAX) ||
    !readMPUWord(0x3D, rawAY) ||
    !readMPUWord(0x3F, rawAZ) ||
    !readMPUWord(0x43, rawGX) ||
    !readMPUWord(0x45, rawGY) ||
    !readMPUWord(0x47, rawGZ)
  ) {

    mpuValid = false;

    Serial.println("MPU communication error!");

    return false;
  }

  // Convert raw accelerometer values into g

  ax = rawAX / 16384.0;
  ay = rawAY / 16384.0;
  az = rawAZ / 16384.0;

  // Convert raw gyroscope values into degrees/second

  gx = rawGX / 131.0;
  gy = rawGY / 131.0;
  gz = rawGZ / 131.0;

  // Calculate acceleration magnitude

  accelerationMagnitude = sqrtf(
    ax * ax +
    ay * ay +
    az * az
  );

  // Approximate vibration deviation from 1g

  vibration = fabsf(
    accelerationMagnitude - 1.0
  );

  mpuValid = true;

  return true;
}

// ==================================================
// 12. SENSOR HEALTH CHECK
// ==================================================

void readSensors() {

  // Read DHT11

  temperature = dht.readTemperature();
  humidity = dht.readHumidity();

  dhtValid =
    isfinite(temperature) &&
    isfinite(humidity) &&
    temperature >= 0.0 &&
    temperature <= 50.0 &&
    humidity >= 0.0 &&
    humidity <= 100.0;

  // Read LDR

  lightValue = analogRead(LDR_PIN);

  // Read MPU

  readMPU();

  Serial.print("DHT health: ");
  Serial.println(dhtValid ? "OK" : "FAULT");

  Serial.print("MPU health: ");
  Serial.println(mpuValid ? "OK" : "FAULT");
}

// ==================================================
// 13. SYSTEM STATUS
// ==================================================

void calculateStatus() {

  currentStatus = NORMAL;

  // Check critical conditions first

  if (
    (dhtValid && temperature >= TEMP_CRITICAL_C) ||
    (mpuValid && vibration >= VIBRATION_CRITICAL_G)
  ) {

    currentStatus = CRITICAL;
    return;
  }

  // Check warning conditions

  if (
    (dhtValid && temperature >= TEMP_WARNING_C) ||
    (mpuValid && vibration >= VIBRATION_WARNING_G)
  ) {

    currentStatus = WARNING;
    return;
  }

  // Sensor fault if no valid sensor data is available
  // for either sensor.

  if (!dhtValid || !mpuValid) {

    currentStatus = FAULT;
  }
}

// ==================================================
// 14. GET STATUS TEXT
// ==================================================

const char* getStatusText() {

  switch (currentStatus) {

    case NORMAL:
      return "NORMAL";

    case WARNING:
      return "WARNING";

    case CRITICAL:
      return "CRITICAL";

    case FAULT:
      return "FAULT";

    default:
      return "UNKNOWN";
  }
}

// ==================================================
// 15. LED AND BUZZER CONTROL
// ==================================================

void updateIndicators() {

  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(YELLOW_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);

  unsigned long now = millis();

  bool buzzerOn = false;

  if (currentStatus == NORMAL) {

    digitalWrite(GREEN_LED_PIN, HIGH);
  }

  else if (currentStatus == WARNING) {

    digitalWrite(YELLOW_LED_PIN, HIGH);

    buzzerOn = (now % 1000 < 200);
  }

  else if (currentStatus == CRITICAL) {

    digitalWrite(RED_LED_PIN, HIGH);

    buzzerOn = (now % 300 < 150);
  }

  else if (currentStatus == FAULT) {

    // Alternate yellow and red for sensor fault

    if (now % 1000 < 500) {
      digitalWrite(YELLOW_LED_PIN, HIGH);
    } else {
      digitalWrite(RED_LED_PIN, HIGH);
    }

    buzzerOn = (now % 1000 < 100);
  }

  digitalWrite(
    BUZZER_PIN,
    buzzerOn ? HIGH : LOW
  );
}

// ==================================================
// 16. OLED DISPLAY
// ==================================================

void updateOLED() {

  display.clearDisplay();

  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);

  display.println("INDUSTRIAL MONITOR");
  display.println("---------------------");

  display.print("Temp: ");

  if (!dhtValid) {
    display.println("Sensor Error");
  } else {
    display.print(temperature, 1);
    display.println(" C");
  }

  display.print("Humidity: ");

  if (!dhtValid) {
    display.println("Sensor Error");
  } else {
    display.print(humidity, 1);
    display.println(" %");
  }

  display.print("Vibration: ");

  if (!mpuValid) {
    display.println("Sensor Error");
  } else {
    display.print(vibration, 2);
    display.println(" g");
  }

  display.print("Light: ");
  display.println(lightValue);

  display.print("Status: ");
  display.println(getStatusText());

  display.display();
}

// ==================================================
// 17. WIFI CONNECTION
// ==================================================

void connectWiFi() {

  Serial.print("Connecting to Wi-Fi");

  WiFi.mode(WIFI_STA);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startTime = millis();

  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - startTime < 20000
  ) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {

    Serial.println("Wi-Fi connected!");

    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
  }

  else {

    Serial.println("Wi-Fi connection timed out.");
  }
}

// ==================================================
// 18. MQTT CONNECTION
// ==================================================

void reconnectMQTT() {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (mqttClient.connected()) {
    return;
  }

  static unsigned long lastAttempt = 0;

  if (millis() - lastAttempt < 3000) {
    return;
  }

  lastAttempt = millis();

  String clientId = "ESP32-Industrial-";

  clientId += String(
    (uint32_t)ESP.getEfuseMac(),
    HEX
  );

  Serial.print("Connecting to MQTT...");

  if (mqttClient.connect(clientId.c_str())) {

    Serial.println("connected!");
  }

  else {

    Serial.print("Failed, state = ");
    Serial.println(mqttClient.state());
  }
}

// ==================================================
// 19. PUBLISH SENSOR DATA
// ==================================================

void publishSensorData() {

  if (!mqttClient.connected()) {

    Serial.println(
      "MQTT not connected; data not published."
    );

    return;
  }

  char payload[512];

  snprintf(
    payload,
    sizeof(payload),

    "{\"device\":\"ESP32\",\"sensor\":\"industrial-monitor\","
    "\"temperature\":%.2f,\"humidity\":%.2f,\"light\":%d,"
    "\"ax\":%.4f,\"ay\":%.4f,\"az\":%.4f,"
    "\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f,"
    "\"dht_valid\":%s,\"mpu_valid\":%s,"
    "\"uptime_ms\":%lu}",

    dhtValid ? temperature : -1.0,
    dhtValid ? humidity : -1.0,
    lightValue,

    ax, ay, az,

    gx, gy, gz,

    dhtValid ? "true" : "false",
    mpuValid ? "true" : "false",

    (unsigned long)(millis() - systemStartTime)
  );

  Serial.print("MQTT payload: ");
  Serial.println(payload);

  if (mqttClient.publish(MQTT_TOPIC, payload)) {

    Serial.println("MQTT publish successful!");
  }

  else {

    Serial.println("MQTT publish failed.");
  }
}

// ==================================================
// 20. SETUP
// ==================================================

void setup() {

  Serial.begin(115200);

  delay(500);

  // Configure output pins

  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(YELLOW_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(YELLOW_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // Initialize DHT11

  dht.begin();

  // Initialize I2C

  Wire.begin(SDA_PIN, SCL_PIN);

  // Initialize OLED

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    OLED_ADDRESS
  )) {

    Serial.println("OLED initialization failed!");
  }

  else {

    display.clearDisplay();

    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);

    display.println("Industrial Monitor");
    display.println("Starting...");

    display.display();
  }

  // Initialize MPU

  mpuInitialized = initializeMPU();

  if (mpuInitialized) {

    Serial.println("MPU initialized successfully.");
  }

  else {

    Serial.println("FAULT: MPU initialization failed.");
  }

  // Record startup time

  systemStartTime = millis();

  // Connect Wi-Fi

  connectWiFi();

  // Configure MQTT

  mqttClient.setServer(
    MQTT_BROKER,
    MQTT_PORT
  );

  mqttClient.setBufferSize(512);

  Serial.println("System setup complete.");
}

// ==================================================
// 21. MAIN LOOP
// ==================================================

void loop() {

  // Maintain Wi-Fi connection

  if (WiFi.status() != WL_CONNECTED) {

    connectWiFi();
  }

  // Maintain MQTT connection

  reconnectMQTT();

  mqttClient.loop();

  // Keep buzzer timing responsive

  updateIndicators();

  unsigned long currentTime = millis();

  // Read sensors every 3 seconds

  if (
    currentTime - lastSensorRead >= SENSOR_INTERVAL
  ) {

    lastSensorRead = currentTime;

    // Read all sensors and validate them

    readSensors();

    // Calculate equipment status

    calculateStatus();

    // Update indicators

    updateIndicators();

    // Update OLED

    updateOLED();

    // Print readings

    Serial.println();
    Serial.println("===== SENSOR READINGS =====");

    Serial.print("Temperature: ");

    if (dhtValid) {
      Serial.println(temperature);
    } else {
      Serial.println("INVALID");
    }

    Serial.print("Humidity: ");

    if (dhtValid) {
      Serial.println(humidity);
    } else {
      Serial.println("INVALID");
    }

    Serial.print("Light: ");
    Serial.println(lightValue);

    Serial.print("MPU health: ");
    Serial.println(mpuValid ? "OK" : "FAULT");

    if (mpuValid) {

      Serial.print("Acceleration X: ");
      Serial.println(ax);

      Serial.print("Acceleration Y: ");
      Serial.println(ay);

      Serial.print("Acceleration Z: ");
      Serial.println(az);

      Serial.print("Vibration: ");
      Serial.println(vibration);
    }

    Serial.print("Status: ");
    Serial.println(getStatusText());

    // Publish MQTT data

    publishSensorData();

    Serial.println("===========================");
  }

  delay(10);
}
