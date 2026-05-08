#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------- WiFi ----------
const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASS";

// ---------- MQTT ----------
const char* mqtt_server = "YOUR_BROKER_IP";

WiFiClient espClient;
PubSubClient client(espClient);

// ---------- Topics ----------
const char* subscribe_topic = "raw/sensor/data";
const char* publish_topic = "processed/sensor/data";

// ---------- Rolling Window ----------
#define WINDOW_SIZE 20

float temp_window[WINDOW_SIZE];
float vib_window[WINDOW_SIZE];
float curr_window[WINDOW_SIZE];

int index_ptr = 0;
bool window_full = false;

// ---------- Utility Functions ----------

float compute_mean(float arr[]) {
  float sum = 0;
  for (int i = 0; i < WINDOW_SIZE; i++) sum += arr[i];
  return sum / WINDOW_SIZE;
}

float compute_std(float arr[], float mean) {
  float sum = 0;
  for (int i = 0; i < WINDOW_SIZE; i++) {
    float diff = arr[i] - mean;
    sum += diff * diff;
  }
  return sqrt(sum / WINDOW_SIZE);
}

bool is_anomaly(float value, float arr[]) {
  if (!window_full) return false;

  float mean = compute_mean(arr);
  float std = compute_std(arr, mean);

  if (std == 0) return false;

  return abs(value - mean) > 2.5 * std;
}

void update_window(float arr[], float value) {
  arr[index_ptr] = value;
}

// ---------- MQTT Callback ----------

void callback(char* topic, byte* payload, unsigned int length) {

  StaticJsonDocument<200> doc;
  deserializeJson(doc, payload, length);

  float temp = doc["temperature"];
  float vib = doc["vibration"];
  float current = doc["current"];

  // ---------- Anomaly Detection ----------
  bool temp_alert = is_anomaly(temp, temp_window);
  bool vib_alert = is_anomaly(vib, vib_window);
  bool curr_alert = is_anomaly(current, curr_window);

  String health = "HEALTHY";
  if (temp_alert || vib_alert || curr_alert) {
    health = "ANOMALY";
  }

  // ---------- Update windows ----------
  update_window(temp_window, temp);
  update_window(vib_window, vib);
  update_window(curr_window, current);

  index_ptr++;
  if (index_ptr >= WINDOW_SIZE) {
    index_ptr = 0;
    window_full = true;
  }

  // ---------- Create Output JSON ----------
  StaticJsonDocument<200> outDoc;

  outDoc["temperature"] = temp;
  outDoc["vibration"] = vib;
  outDoc["current"] = current;
  outDoc["health"] = health;

  char buffer[200];
  serializeJson(outDoc, buffer);

  client.publish(publish_topic, buffer);

  Serial.println(buffer);
}

// ---------- MQTT Setup ----------

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting MQTT...");
    if (client.connect("ESP32_Anomaly_Node")) {
      Serial.println("Connected");
      client.subscribe(subscribe_topic);
    } else {
      Serial.println("Retrying...");
      delay(2000);
    }
  }
}

// ---------- Setup ----------

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

// ---------- Loop ----------

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}