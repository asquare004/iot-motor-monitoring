#ifndef AWS_CONNECTION_H
#define AWS_CONNECTION_H

#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "Config.h"

extern RelayController relay;

BearSSL::WiFiClientSecure net;
PubSubClient mqttClient(net);


/* ---------------- MQTT Callback ---------------- */

void mqttCallback(char* topic, byte* payload, unsigned int length){

    StaticJsonDocument<256> doc;
    deserializeJson(doc,payload);

    String action = doc["action"];
    String machine = doc["machine_id"];

    if(machine == MACHINE_ID){

        if(action=="ON" || action=="OFF"){

            relay.setState(action);

            Serial.print("Relay set to ");
            Serial.println(action);
        }
    }
}

/* ---------------- AWS Connection ---------------- */

void connectAWS(){

    /* Attach certificates */

    BearSSL::X509List ca(AWS_CERT_CA);
    BearSSL::X509List client_crt(AWS_CERT_CRT);
    BearSSL::PrivateKey key(AWS_CERT_PRIVATE);

    net.setTrustAnchors(&ca);
    net.setClientRSACert(&client_crt, &key);

    net.setBufferSizes(512,512);

    mqttClient.setServer(AWS_ENDPOINT,8883);
    mqttClient.setCallback(mqttCallback);

    while(!mqttClient.connected()){

        Serial.println("Connecting AWS IoT...");

        if(mqttClient.connect(CLIENT_ID)){

            Serial.println("Connected");

            mqttClient.subscribe(SIGNAL_TOPIC);
        }
        else{

            Serial.print("Failed rc=");
            Serial.println(mqttClient.state());

            delay(2000);
        }
    }
}

#endif