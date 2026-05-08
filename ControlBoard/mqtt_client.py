"""
Singleton MQTT client for the Control Board.

- Publishes ON/OFF signals to machine/signal
- Subscribes to cloud/verdict + sensors/data for live status
"""

import json
import os
import threading

from awscrt import mqtt
from awsiot import mqtt_connection_builder
from dotenv import load_dotenv

load_dotenv("Backend/.env")


class MQTTClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._machine_status = {}
        self._status_lock = threading.Lock()

        endpoint = os.getenv("AWS_IOT_ENDPOINT")
        cert_path = os.getenv("AWS_IOT_CERT_PATH", "Backend/Utils/Certificates/controlboardbackend-certificate.pem.crt")
        key_path = os.getenv("AWS_IOT_KEY_PATH", "Backend/Utils/Keys/controlboardbackend-private.pem.key")
        ca_path = os.getenv("AWS_IOT_CA_PATH", "Backend/Utils/CA/AmazonRootCA1.pem")
        client_id = os.getenv("CLIENT_ID", "control-board-client")

        self._signal_topic = os.getenv("MACHINE_SIGNAL_TOPIC", "machine/signal")
        self._verdict_topic = os.getenv("CLOUD_VERDICT_TOPIC", "cloud/verdict")
        self._sensor_topic = os.getenv("SENSOR_DATA_TOPIC", "sensors/data")

        self._connection = mqtt_connection_builder.mtls_from_path(
            endpoint=endpoint,
            cert_filepath=cert_path,
            pri_key_filepath=key_path,
            ca_filepath=ca_path,
            client_id=client_id,
            clean_session=True,
            keep_alive_secs=30,
        )

        print("[MQTT] Connecting to AWS IoT Core...")
        self._connection.connect().result()
        print("[MQTT] Connected!")

        # Subscribe to cloud/verdict for AI health assessments
        self._connection.subscribe(
            topic=self._verdict_topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_verdict,
        )
        print(f"[MQTT] Subscribed to {self._verdict_topic}")

        # Subscribe to sensors/data for live switch state
        self._connection.subscribe(
            topic=self._sensor_topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_sensor_data,
        )
        print(f"[MQTT] Subscribed to {self._sensor_topic}")

    # ── callbacks ──────────────────────────────────────────────

    def _on_verdict(self, topic, payload, dup, qos, retain, **kwargs):
        try:
            data = json.loads(payload.decode())
            mid = data.get("machine_id")
            if not mid:
                return
            with self._status_lock:
                entry = self._machine_status.setdefault(mid, {})
                entry.update(
                    {
                        "machine_id": mid,
                        "health": data.get("health", entry.get("health")),
                        "temperature": data.get("temperature", entry.get("temperature")),
                        "vibration": data.get("vibration", entry.get("vibration")),
                        "current": data.get("current", entry.get("current")),
                        "switch_state": data.get("switch_state", entry.get("switch_state")),
                        "anomaly_prob": data.get("anomaly_prob", entry.get("anomaly_prob")),
                        "normal_score": data.get("normal_score", entry.get("normal_score")),
                        "issues": data.get("issues", entry.get("issues", [])),
                        "stopping_required": data.get("stopping_required", entry.get("stopping_required")),
                        "timestamp": data.get("timestamp", entry.get("timestamp")),
                    }
                )
        except Exception as e:
            print(f"[MQTT] verdict parse error: {e}")

    def _on_sensor_data(self, topic, payload, dup, qos, retain, **kwargs):
        try:
            data = json.loads(payload.decode())
            mid = data.get("machine_id")
            if not mid:
                return
            with self._status_lock:
                entry = self._machine_status.setdefault(mid, {})
                # Sensor data contains the real-time switch state
                entry.update(
                    {
                        "machine_id": mid,
                        "switch_state": data.get("switch_state", entry.get("switch_state")),
                        "temperature": data.get("temperature", entry.get("temperature")),
                        "vibration": data.get("vibration", entry.get("vibration")),
                        "current": data.get("current", entry.get("current")),
                        "edge_health": data.get("health", entry.get("edge_health")),
                    }
                )
        except Exception as e:
            print(f"[MQTT] sensor parse error: {e}")

    # ── public API ─────────────────────────────────────────────

    def send_signal(self, machine_id: str, action: str):
        """Publish an ON/OFF signal to machine/signal."""
        payload = {"machine_id": machine_id, "action": action}
        self._connection.publish(
            topic=self._signal_topic,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
        print(f"[MQTT] Signal sent: {machine_id} → {action}")

    def get_status(self, machine_id: str = None):
        """Return latest status dict for one or all machines."""
        with self._status_lock:
            if machine_id:
                return dict(self._machine_status.get(machine_id, {}))
            return {k: dict(v) for k, v in self._machine_status.items()}
