#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include "Config.h"
#include "SensorManager.h"
#include "EdgeAnomalyDetector.h"
#include "RelayController.h"
#include "AWSConnection.h"

SensorManager sensors;
EdgeAnomalyDetector detector;
RelayController relay;

unsigned long lastPublish = 0;

void connectWiFi(){

    WiFi.begin(WIFI_SSID,WIFI_PASSWORD);

    Serial.print("Connecting WiFi");

    while(WiFi.status()!=WL_CONNECTED){

        delay(500);
        Serial.print(".");
    }

    Serial.println("Connected");
}

void setup(){

    Serial.begin(115200);

    sensors.begin();

    relay.begin();

    connectWiFi();

    connectAWS();
}

void publishData(){

    float temp = sensors.readTemperature();
    float vib = sensors.readVibration();
    float current = sensors.readCurrent();

    bool tempAlert = detector.tempAnomaly(temp);
    bool vibAlert = detector.vibAnomaly(vib);
    bool currAlert = detector.currentAnomaly(current);

    String verdict = "HEALTHY";

    if(tempAlert || vibAlert || currAlert)
        verdict = "ANOMALY";

    detector.updateTemp(temp);
    detector.updateVib(vib);
    detector.updateCurrent(current);

    StaticJsonDocument<256> doc;

    doc["temperature"] = temp;
    doc["vibration"] = vib;
    doc["current"] = current;
    doc["machine_id"] = MACHINE_ID;
    doc["health"] = verdict;
    doc["switch_state"] = relay.getState();
    doc["advertising_latency_ms"] = ADVERTISING_LATENCY_MS;

    char buffer[256];

    serializeJson(doc,buffer);

    mqttClient.publish(SENSOR_DATA_TOPIC,buffer);

    Serial.println(buffer);
}

void loop(){

    if(!mqttClient.connected())
        connectAWS();

    mqttClient.loop();

    if(millis()-lastPublish > ADVERTISING_LATENCY_MS){

        lastPublish = millis();

        publishData();
    }
}