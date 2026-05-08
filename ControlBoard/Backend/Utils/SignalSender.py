import json
from awscrt import mqtt
from awsiot import mqtt_connection_builder

from dotenv import load_dotenv
import os

load_dotenv()


def publish_machine_signal(machine_id: str, turn_on: bool):
    """
    Publish a machine control signal to AWS IoT Core via MQTT.

    Args:
        machine_id (str): The unique identifier of the machine to control.
        turn_on (bool): True to turn the machine ON, False to turn it OFF.

    Returns:
        None

    Raises:
        Exception: If connection to AWS IoT fails or message publishing fails.
    """
    endpoint = os.getenv("AWS_IOT_ENDPOINT")
    cert_path = os.getenv("AWS_IOT_CERT_PATH", "Backend/Utils/Certificates/controlboardbackend-certificate.pem.crt")
    key_path = os.getenv("AWS_IOT_KEY_PATH", "Backend/Utils/Keys/controlboardbackend-private.pem.key")
    ca_path = os.getenv("AWS_IOT_CA_PATH", "Backend/Utils/CA/AmazonRootCA1.pem")
    client_id = os.getenv("CLIENT_ID", "control-board-backend")

    payload = {
        "machine_id": machine_id,
        "action": "ON" if turn_on else "OFF",
        "source": "MANUAL_CONTROL_BOARD",
    }

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=cert_path,
        pri_key_filepath=key_path,
        ca_filepath=ca_path,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=30
    )

    # Connect
    connect_future = mqtt_connection.connect()
    connect_future.result()

    # Publish
    mqtt_connection.publish(
        topic=os.getenv("MACHINE_SIGNAL_TOPIC"),
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    # Disconnect
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
