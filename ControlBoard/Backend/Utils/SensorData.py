import json
import threading
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

import os
from dotenv import load_dotenv
load_dotenv()

def start_cloud_data_subscription(
    state_dict: dict,
    lock: threading.Lock
):
    """
    Starts AWS IoT MQTT subscription and updates state_dict.

    state_dict → dict reference supplied by caller
    """

    endpoint = os.getenv("AWS_IOT_ENDPOINT")
    root_ca = os.getenv("AWS_IOT_CA_PATH", "Backend/Utils/CA/AmazonRootCA1.pem")
    private_key = os.getenv("AWS_IOT_KEY_PATH", "Backend/Utils/Keys/controlboardbackend-private.pem.key")
    certificate = os.getenv("AWS_IOT_CERT_PATH", "Backend/Utils/Certificates/controlboardbackend-certificate.pem.crt")
    client_id = os.getenv("CLIENT_ID", "control-board-backend")
    topic = os.getenv("CLOUD_VERDICT_TOPIC")

    def message_callback(client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))

            machine_id = payload.get("machine_id")
            cloud_data=payload
    
            if machine_id and cloud_data:
                with lock:
                    state_dict[machine_id] = cloud_data

                print(f"[IoT] {machine_id} → {cloud_data}")

        except Exception as e:
            print("[IoT] Error:", e)

    mqtt_client = AWSIoTMQTTClient(clientID=client_id,cleanSession=False)
    mqtt_client.configureEndpoint(endpoint, 8883)
    mqtt_client.configureCredentials(root_ca, private_key, certificate)

    print("[IoT] Connecting...")
    if not mqtt_client.connect():
        raise Exception("Failed to connect to AWS IoT")
    print("[IoT] Connected")

    mqtt_client.subscribe(topic, 1, message_callback)
    print(f"[IoT] Subscribed to {topic}")

    return (state_dict, lock)
