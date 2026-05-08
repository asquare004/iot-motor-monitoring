from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader
from fastapi.staticfiles import StaticFiles
from awscrt import mqtt
from awsiot import mqtt_connection_builder
import json
import threading

import os
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "twin_frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

# Latest state per machine_id
LATEST: Dict[str, Dict[str, Any]] = {}
LATEST_LOCK = threading.Lock()

# --- AWS IoT Config ---
ENDPOINT = os.getenv("ENDPOINT") or os.getenv("AWS_IOT_ENDPOINT")
CLIENT_ID = os.getenv("CLIENT_ID", "twin-model-client")
PATH_TO_CERT = os.getenv("AWS_IOT_CERT_PATH", "Certificates/twinmodel-certificate.pem.crt")
PATH_TO_KEY = os.getenv("AWS_IOT_KEY_PATH", "Keys/twinmodel-private.pem.key")
PATH_TO_ROOT_CA = os.getenv("AWS_IOT_CA_PATH", "CA/AmazonRootCA1.pem")

TOPIC = os.getenv("CLOUD_VERDICT_TOPIC", "cloud/verdict")

templatesEnv=Environment(loader=FileSystemLoader("twin_frontend"))

def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    try:
        message = json.loads(payload.decode())

        # Expected payload:
        # {"machine_id": "sensor_1", "temperature": 23.4}
        device_id = message.get("machine_id")
        if device_id is None:
            print("Received message without machine_id, ignoring.")
            return

        with LATEST_LOCK:
            LATEST[device_id] = message

        print(f"Updated {device_id}: {message}")

    except Exception as e:
        print("Error processing message:", e)


def on_connection_interrupted(connection, error, **kwargs):
    print("AWSIoT : Connection interrupted:", error)

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("AWSIoT : Connection resumed")

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=PATH_TO_CERT,
    pri_key_filepath=PATH_TO_KEY,
    ca_filepath=PATH_TO_ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=60,
    on_connection_resumed=on_connection_resumed,
    on_connection_interrupted=on_connection_interrupted
)

print("Connecting to AWS IoT...")
connect_future = mqtt_connection.connect()
connect_future.result()
print("Connected to AWS IoT")

print(f"Subscribing to {TOPIC}...")
subscribe_future, _ = mqtt_connection.subscribe(
    topic=TOPIC,
    qos=mqtt.QoS.AT_MOST_ONCE,
    callback=on_message_received
)
subscribe_future.result()
print("Subscribed")

# Serve static assets under /static
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/{machine_id}")
def root(request: Request, machine_id: str):
    template = templatesEnv.get_template("index.html")
    html = template.render(machine_id=machine_id)
    return HTMLResponse(content=html)



@app.post("/twin/update")
def twin_update(payload: Dict[str, Any]):
    machine_id = payload.get("machine_id")
    if not machine_id:
        raise HTTPException(status_code=400, detail="machine_id is required")

    with LATEST_LOCK:
        LATEST[machine_id] = payload

    return {"ok": True}


@app.get("/machine/{machine_id}")
def get_machine(machine_id: str):
    with LATEST_LOCK:  
        return LATEST.get(machine_id, {"machine_id": machine_id})
