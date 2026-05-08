from awsiot import mqtt_connection_builder
from Cloud.MessageHandlers import create_on_message_received_callback
from awscrt import mqtt

import os
from dotenv import load_dotenv
load_dotenv()

def on_connection_interrupted(connection, error, **kwargs):
    print("AWSIoT : Connection interrupted:", error)

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("AWSIoT : Connection resumed")

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=os.getenv("AWS_IOT_ENDPOINT"),
    cert_filepath=os.getenv("AWS_IOT_CERT_PATH", "Certificates/cloud-certificate.pem.crt"),
    pri_key_filepath=os.getenv("AWS_IOT_KEY_PATH", "Keys/cloud-private.pem.key"),
    ca_filepath=os.getenv("AWS_IOT_CA_PATH", "CA/AmazonRootCA1.pem"),
    client_id=os.getenv("CLIENT_ID"),
    clean_session=False,
    keep_alive_secs=60,
    on_connection_interrupted=on_connection_interrupted,
    on_connection_resumed=on_connection_resumed
)

print("Connecting to AWS IoT...")
mqtt_connection.connect().result()
print("Connected!")

topic = os.getenv("SENSOR_DATA_TOPIC")
print("Topic =", topic)

subscribe_future,_ = mqtt_connection.subscribe(
    topic=os.getenv("SENSOR_DATA_TOPIC"),
    qos=mqtt.QoS.AT_MOST_ONCE,
    callback=create_on_message_received_callback(mqtt_connection)
)
subscribe_future.result(timeout=10)

print("Listening for sensor data...")

import time
while True:
    time.sleep(1)
