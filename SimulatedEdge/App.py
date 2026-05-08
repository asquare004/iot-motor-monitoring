import os
from dotenv import load_dotenv
import threading
import json
import time
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from EdgeAnomalyDetector import EdgeAnomalyDetector
from MachineSimulator import MachineSimulator

load_dotenv()

CLIENT_ID = os.environ["MACHINE_ID"] + "_simulator_client"
ENDPOINT = os.environ.get("ENDPOINT") or os.environ["AWS_IOT_ENDPOINT"]
MACHINE_ID = os.environ["MACHINE_ID"]
SENSOR_DATA_TOPIC = os.environ["SENSOR_DATA_TOPIC"]
SIGNAL_TOPIC = os.environ["SIGNAL_TOPIC"]
PUBLISH_INTERVAL_MS = int(os.environ.get("ADVERTISING_LATENCY_MS", "5000"))
STARTUP_WARMUP_SAMPLES = int(os.environ.get("STARTUP_WARMUP_SAMPLES", "4"))

mqtt = AWSIoTMQTTClient(CLIENT_ID,cleanSession=True)
mqtt.configureEndpoint(ENDPOINT, 8883)
mqtt.configureCredentials(
    os.getenv("AWS_IOT_CA_PATH", "CA/AmazonRootCA1.pem"),
    os.getenv("AWS_IOT_KEY_PATH", "Keys/SimulatedMachine01-private.pem.key"),
    os.getenv("AWS_IOT_CERT_PATH", "Certificates/SimulatedMachine01-certificate.pem.crt"),
)

mqtt.connect()

relay_state = {"switch_state": "ON", "control_source": "INITIAL"}
relay_lock = threading.Lock()
run_session_id = 1
power_on_samples = 0
state_sample_index = 0
operating_state = "STARTING"
last_switch_state = relay_state["switch_state"]

# Handle relay commands
def relay_callback(client, userdata, message):
    global relay_state
    payload = json.loads(message.payload.decode("utf-8"))

    if payload["action"] in ["ON", "OFF"] and payload.get("machine_id") == MACHINE_ID:
        with relay_lock:
            relay_state["switch_state"] = payload["action"]
            relay_state["control_source"] = payload.get("source", "UNKNOWN")
            print("Relay set to:", relay_state["switch_state"])

mqtt.subscribe(SIGNAL_TOPIC, 1, relay_callback)

print("Simulator running...")

edgeAnomalyDetector = EdgeAnomalyDetector()
machineSimulator = MachineSimulator()

while True:
    with relay_lock:
        switch_state = relay_state["switch_state"]
        control_source = relay_state["control_source"]
        if switch_state != last_switch_state:
            edgeAnomalyDetector.reset()
            if switch_state == "ON":
                run_session_id += 1
                power_on_samples = 0
                state_sample_index = 0
                operating_state = "STARTING"
            else:
                power_on_samples = 0
                state_sample_index = 0
                operating_state = "OFF"
            last_switch_state = switch_state
        temp, vib, current = machineSimulator.simulate_machine(switch_state)

    verdict = "IDLE"
    if switch_state == "ON":
        power_on_samples += 1

        if power_on_samples <= STARTUP_WARMUP_SAMPLES:
            operating_state = "STARTING"
            state_sample_index = power_on_samples
            verdict = "STARTING"
        else:
            if operating_state != "RUNNING":
                edgeAnomalyDetector.reset()
                state_sample_index = 0

            operating_state = "RUNNING"
            state_sample_index += 1

            temp_alert = edgeAnomalyDetector.check_temperature_anomaly(temp)
            vib_alert = edgeAnomalyDetector.check_vibration_anomaly(vib)
            curr_alert = edgeAnomalyDetector.check_current_anomaly(current)

            verdict = "ANOMALY" if (temp_alert or vib_alert or curr_alert) else "HEALTHY"

            edgeAnomalyDetector.update_temperature_window(temp)
            edgeAnomalyDetector.update_vibration_window(vib)
            edgeAnomalyDetector.update_current_window(current)
    else:
        operating_state = "OFF"
        state_sample_index += 1
        power_on_samples = 0
        verdict = "IDLE"

    sensor_payload = {
        "temperature": temp,
        "vibration": vib,
        "current": current,
        "machine_id": MACHINE_ID,
        "health": verdict,
        "advertising_latency_ms": PUBLISH_INTERVAL_MS,
        "switch_state": switch_state,
        "operating_state": operating_state,
        "run_session_id": run_session_id,
        "state_sample_index": state_sample_index,
        "ml_eligible": operating_state == "RUNNING",
        "control_source": control_source,
    }

    mqtt.publish(SENSOR_DATA_TOPIC, json.dumps(sensor_payload), 1)
    print("Published:", sensor_payload)

    time.sleep(PUBLISH_INTERVAL_MS / 1000)
