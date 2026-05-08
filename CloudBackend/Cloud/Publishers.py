from awscrt import mqtt
import json
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv()


def publish_ai_verdict(sensor_data, verdict,mqtt_connection):
    payload = {
        "machine_id": sensor_data["machine_id"],
        "timestamp": datetime.utcnow().isoformat(),
        "temperature": sensor_data.get("temperature"),
        "vibration": sensor_data.get("vibration"),
        "current": sensor_data.get("current"),
        "switch_state": sensor_data.get("switch_state", "unknown"),
        "operating_state": verdict.get("operating_state", sensor_data.get("operating_state")),
        "control_source": sensor_data.get("control_source", "UNKNOWN"),
        "run_session_id": verdict.get("run_session_id", sensor_data.get("run_session_id")),
        "state_sample_index": verdict.get("state_sample_index", sensor_data.get("state_sample_index")),
        "detection_active": verdict.get("detection_active"),
        "health": verdict.get("health_status"),
        "health_score": verdict.get("health_score"),
        "issues": verdict.get("issues", []),
        "stopping_required": verdict.get("stopping_required"),
        "pending_stop_confirmation": verdict.get("pending_stop_confirmation", False),
        "anomaly_streak": verdict.get("anomaly_streak", 0),
        "required_anomaly_streak": verdict.get("required_anomaly_streak", 0),
        "normal_score": verdict.get("normal_score"),
        "anomaly_prob": verdict.get("anomaly_prob"),
    }

    pub_future,packet_id=mqtt_connection.publish(
        topic=os.getenv("AI_VERDICT_TOPIC"),
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    # try:
    #     pub_future.result(timeout=10)  # shorter + safer
    #     print(f"PUBACK received (packet {packet_id})")

    # except Exception as e:
    #     print(f"PUBACK timeout (packet {packet_id}) → {e}")

    print("AI verdict published")

def publish_stop_signal(mqtt_connection, machine_id):
    payload = {
        "machine_id": machine_id,
        "action": "OFF",
        "source": "AUTO_PROTECTION",
    }

    pub_future,packet_id=mqtt_connection.publish(
        topic=os.getenv("SIGNAL_TOPIC"),
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    # try:
    #     pub_future.result(timeout=10)  # shorter + safer
    #     print(f"PUBACK received (packet {packet_id})")

    # except Exception as e:
    #     print(f"PUBACK timeout (packet {packet_id}) → {e}")

    print("STOP signal sent")
