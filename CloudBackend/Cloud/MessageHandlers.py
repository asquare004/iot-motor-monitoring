import json
import os
from AI.predictions import evaluate_sensor_data
from Cloud.ProtectionController import ProtectionController
from Cloud.Publishers import publish_ai_verdict, publish_stop_signal
from Database.utils import store_metrics
from Cloud.EmailSender import send_stop_email
from Cloud.TwinClient import push_to_twin

def create_on_message_received_callback(mqtt_connection):
    protection_controller = ProtectionController()

    def on_message_received(topic, payload, **kwargs):
        if(topic != os.getenv("SENSOR_DATA_TOPIC")):
            return
        try:
            sensor_data = json.loads(payload.decode())
            print(f"Received on {topic}: {sensor_data}")

            verdict = evaluate_sensor_data(sensor_data)
            verdict = protection_controller.apply(sensor_data, verdict)
            print("AI verdict:", verdict)

            store_metrics(sensor_data, verdict)
            # push_to_twin(sensor_data, verdict)
            publish_ai_verdict(sensor_data, verdict,mqtt_connection)

            if verdict["stopping_required"]:
                publish_stop_signal(mqtt_connection, sensor_data["machine_id"])
                if sensor_data["switch_state"]=="ON":
                    send_stop_email(sensor_data, verdict)

        except Exception as e:
            print("Processing error:", repr(e))

    return on_message_received
