import os
from datetime import datetime
from influxdb_client import InfluxDBClient, Point

from dotenv import load_dotenv
load_dotenv()

influx_client = InfluxDBClient(
    url=os.getenv("INFLUXDB_URL"),
    token=os.getenv("INFLUXDB_TOKEN"),
    org=os.getenv("INFLUXDB_ORG")
)
write_api = influx_client.write_api()

def store_metrics(sensor_data, verdict):
    health_score = verdict.get("health_score")
    normal_score = verdict.get("normal_score")
    anomaly_prob = verdict.get("anomaly_prob")
    operating_state = verdict.get("operating_state", sensor_data.get("operating_state", "UNKNOWN"))
    run_session_id = sensor_data.get("run_session_id", 0)
    state_sample_index = sensor_data.get("state_sample_index", 0)
    point = (
        Point("machine_metrics")
        .tag("machine_id", sensor_data["machine_id"])
        .tag("operating_state", operating_state)
        .field("temperature", float(sensor_data["temperature"] if "temperature" in sensor_data else 0.0))
        .field("vibration", float(sensor_data["vibration"] if "vibration" in sensor_data else 0.0))
        .field("current", float(sensor_data["current"] if "current" in sensor_data else 0.0))
        .field("run_session_id", int(run_session_id))
        .field("state_sample_index", int(state_sample_index))
        .field("switch_state", sensor_data["switch_state"] if "switch_state" in sensor_data else "unknown")
        .field("control_source", sensor_data.get("control_source", "UNKNOWN"))
        .field("health", float(health_score if health_score is not None else 0.0))
        .field("health_status", verdict["health_status"] if "health_status" in verdict else "UNKNOWN")
        .field("issues", ",".join(verdict["issues"] if "issues" in verdict else []))
        .field("stopping_required", int(verdict.get("stopping_required", False)))
        .field("pending_stop_confirmation", int(verdict.get("pending_stop_confirmation", False)))
        .field("anomaly_streak", int(verdict.get("anomaly_streak", 0)))
        .field("required_anomaly_streak", int(verdict.get("required_anomaly_streak", 0)))
        .field("detection_active", int(verdict.get("detection_active", False)))
        .field("normal_score", float(normal_score if normal_score is not None else 0.0))
        .field("anomaly_prob", float(anomaly_prob if anomaly_prob is not None else 0.0))
        .time(datetime.utcnow())
    )

    write_api.write(bucket=os.getenv("INFLUXDB_BUCKET"), record=point)
    print("Written to InfluxDB")
