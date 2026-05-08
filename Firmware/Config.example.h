#ifndef CONFIG_H
#define CONFIG_H

// Copy this file to Config.h and replace the placeholder values locally.
// Do not commit Config.h because it contains Wi-Fi and AWS IoT credentials.

#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASSWORD "your-wifi-password"

#define CLIENT_ID "your-device-client-id"
#define MACHINE_ID "machine01"

#define AWS_ENDPOINT "your-aws-iot-endpoint-ats.iot.your-region.amazonaws.com"

#define SENSOR_DATA_TOPIC "sensor/data"
#define SIGNAL_TOPIC "machine/signal"

#define ADVERTISING_LATENCY_MS 5000

// GPIO mapping
#define TEMP_PIN D4
#define VIB_PIN D5
#define CURRENT_PIN A0
#define RELAY_PIN D6

static const char AWS_CERT_CA[] PROGMEM = R"EOF(
PASTE_FULL_AMAZON_ROOT_CA_1_PEM_HERE
)EOF";

static const char AWS_CERT_CRT[] PROGMEM = R"KEY(
PASTE_FULL_DEVICE_CERTIFICATE_PEM_HERE
)KEY";

static const char AWS_CERT_PRIVATE[] PROGMEM = R"KEY(
PASTE_FULL_DEVICE_PRIVATE_KEY_PEM_HERE
)KEY";

#endif
