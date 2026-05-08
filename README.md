# IoT Motor Monitoring and Predictive Maintenance

This project simulates and monitors motor telemetry with AWS IoT Core, InfluxDB, a cloud anomaly-detection backend, a Flask control board, and a FastAPI/Three.js digital twin.

## What Runs

```text
SimulatedEdge/Firmware -> AWS IoT Core -> CloudBackend -> InfluxDB
                                      -> ControlBoard
                                      -> Digital Twin
```

- `SimulatedEdge`: publishes machine telemetry and listens for ON/OFF commands.
- `CloudBackend`: reads telemetry, scores machine health, stores metrics, and publishes verdicts.
- `ControlBoard`: browser dashboard for machine status and manual ON/OFF commands.
- `Digital Twin`: browser visualization of the latest machine state.
- `Firmware`: optional ESP8266 device code for real hardware.

## How The System Works

The application is built around three MQTT topics:

```text
sensor/data      telemetry from the simulator or hardware device
cloud/verdict    health verdicts produced by the cloud backend
machine/signal   ON/OFF commands sent to machines
```

The usual Docker workflow starts six services:

- `influxdb`: local time-series database.
- `iotproject_cloud`: cloud ingestion and anomaly detection backend.
- `simulated_edge_01`: simulated machine with `MACHINE_ID=machine01`.
- `simulated_edge_02`: simulated machine with `MACHINE_ID=machine02`.
- `trainer`: retrains the Isolation Forest model periodically.
- `twin_backend`: serves the digital twin API and frontend.
- `control_board_backend`: serves the operator dashboard.

### SimulatedEdge

Location: `SimulatedEdge/`

`SimulatedEdge/App.py` behaves like a machine connected to AWS IoT Core.

On startup it:

1. Loads `SimulatedEdge/.env`.
2. Connects to AWS IoT using the local certificate files configured by `AWS_IOT_CERT_PATH`, `AWS_IOT_KEY_PATH`, and `AWS_IOT_CA_PATH`.
3. Subscribes to `SIGNAL_TOPIC`, normally `machine/signal`.
4. Publishes telemetry to `SENSOR_DATA_TOPIC`, normally `sensor/data`.

Each loop:

1. Reads the current relay state, either `ON` or `OFF`.
2. Generates sensor values with `MachineSimulator.py`.
3. Uses `EdgeAnomalyDetector.py` for a simple local sigma-threshold health label.
4. Builds a telemetry JSON payload.
5. Publishes the payload to AWS IoT.

Telemetry includes:

```text
machine_id
temperature
vibration
current
health
switch_state
operating_state
run_session_id
state_sample_index
ml_eligible
control_source
```

The simulator tracks machine state carefully:

- `OFF`: relay is off; telemetry is still published for visibility.
- `STARTING`: machine was just turned on; startup samples are excluded from ML scoring.
- `RUNNING`: normal operating state; samples can be used for anomaly detection.

When a message arrives on `machine/signal`, the simulator checks whether the `machine_id` matches its own ID. If it receives `{"action":"OFF"}`, it switches off. If it receives `{"action":"ON"}`, it starts a new run session.

### CloudBackend

Location: `CloudBackend/`

`CloudBackend/Cloud/App.py` is the main cloud service. It connects to AWS IoT Core with mTLS certificates, subscribes to `sensor/data`, and passes each message to `Cloud/MessageHandlers.py`.

For every telemetry message, the cloud backend:

1. Parses the JSON payload.
2. Calls `AI/predictions.py` to classify the latest machine state.
3. Applies stop-confirmation rules from `Cloud/ProtectionController.py`.
4. Stores the sensor data and verdict in InfluxDB through `Database/utils.py`.
5. Publishes a cloud verdict through `Cloud/Publishers.py`.
6. Publishes an automatic OFF command if the reading is critical.
7. Optionally sends an email alert through `Cloud/EmailSender.py` if SMTP settings are configured.

The cloud verdict is published to `AI_VERDICT_TOPIC`, normally `cloud/verdict`, and includes:

```text
machine_id
timestamp
temperature
vibration
current
switch_state
operating_state
health
health_score
issues
stopping_required
pending_stop_confirmation
anomaly_streak
normal_score
anomaly_prob
```

The cloud backend writes to the InfluxDB measurement `machine_metrics`. This gives the dashboard, trainer, and manual database inspection a common time-series history.

### Anomaly Detection

Location: `CloudBackend/AI/`

The ML pipeline is online anomaly detection for motor telemetry.

`AI/predictions.py` is used at runtime:

1. It normalizes the machine context with `runtime_context.py`.
2. It ignores ML scoring for `OFF` and `STARTING` samples.
3. It fetches recent `RUNNING` history for the same machine and run session from InfluxDB.
4. It builds time-series features with `feature_engineering.py`.
5. It loads `AI/models/iforest.joblib` if the trainer has produced one.
6. It combines model scoring with hard safety rules.

Hard safety rules can immediately mark the machine unsafe when values cross configured limits such as `AI_CRITICAL_TEMP`, `AI_CRITICAL_VIB`, or `AI_CRITICAL_CURR`.

`AI/train_iforest.py` runs in the `trainer` container every five minutes. It:

1. Queries recent InfluxDB data.
2. Keeps only `RUNNING` samples.
3. Builds rolling, delta, EWMA, and slope features.
4. Trains an `IsolationForest`.
5. Saves generated model files under `CloudBackend/AI/models/`.

Model files are intentionally ignored by Git because they are generated runtime artifacts. A new clone can start without them; the backend falls back to rule-based behavior until the trainer creates a model.

### InfluxDB

InfluxDB stores telemetry and verdict fields in the `machine_metrics` measurement.

The root `.env` controls initial database setup for Docker:

```text
INFLUXDB_USERNAME
INFLUXDB_PASSWORD
INFLUXDB_ORG
INFLUXDB_BUCKET
INFLUXDB_TOKEN
```

`CloudBackend/.env` must use matching `INFLUXDB_URL`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`, and `INFLUXDB_TOKEN` values so the cloud backend can write data and the trainer can read historical data.

### ControlBoard

Location: `ControlBoard/`

`ControlBoard/app.py` is a Flask web app for operators.

On startup it:

1. Loads `ControlBoard/.env`.
2. Opens or creates the SQLite database configured by `CONTROLBOARD_DB_PATH`.
3. Starts an AWS IoT subscription using `Backend/Utils/SensorData.py`.
4. Serves the login page and dashboard.

The dashboard uses these routes:

```text
GET  /                         dashboard page
GET  /login                    login form
POST /login                    login submit
GET  /logout                   end session
POST /api/control              send ON/OFF command
GET  /api/status               return latest machine states
GET  /api/admin/users          list users
POST /api/admin/users          create users
DELETE /api/admin/users/<id>   delete users
```

`Backend/Utils/SensorData.py` subscribes to `cloud/verdict` and keeps the latest machine state in memory. The dashboard reads that in-memory state through `/api/status`.

`Backend/Utils/SignalSender.py` publishes manual operator commands to `machine/signal`. The simulator or firmware then receives the command and changes relay state.

`init_db.py` creates default local users. These are for local demos only and should be changed before any real use.

### Digital Twin

Location: `Digital Twin/`

`twin_backend.py` is a FastAPI app. It connects to AWS IoT Core, subscribes to `cloud/verdict`, and stores the latest message for each `machine_id` in memory.

It exposes:

```text
GET  /{machine_id}        serves the browser visualization
GET  /machine/{machine_id} returns latest state JSON
POST /twin/update         accepts direct state updates from another service
```

The frontend files live in `Digital Twin/twin_frontend/`. The browser page polls the backend for the selected machine and updates the visual state with the latest temperature, vibration, current, switch state, and health values.

### Firmware

Location: `Firmware/`

The firmware is the hardware version of `SimulatedEdge` for an ESP8266 device.

Important files:

```text
EdgeDevice.ino          main Arduino sketch
Config.example.h        template for Wi-Fi and AWS IoT credentials
AWSConnection.h         Wi-Fi, TLS, MQTT connection, and command subscription
SensorManager.h         sensor reading logic
RelayController.h       relay ON/OFF control
EdgeAnomalyDetector.h   lightweight edge-side anomaly checks
```

To use it, copy `Config.example.h` to `Config.h` and fill in local credentials. `Config.h` is ignored by Git because it contains Wi-Fi and AWS IoT private key material.

At runtime the firmware:

1. Connects to Wi-Fi.
2. Connects to AWS IoT Core over MQTT/TLS.
3. Subscribes to `machine/signal`.
4. Reads sensors.
5. Publishes telemetry to `sensor/data`.
6. Switches the relay when an ON/OFF command arrives.

## Prerequisites

Install:

- Docker Desktop or Docker Engine with Docker Compose
- Git
- An AWS account with AWS IoT Core access

Optional:

- Python 3.11, only if you want to run services without Docker
- Arduino IDE or arduino-cli, only if you want to flash the ESP8266 firmware

## 1. Clone The Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

On Windows PowerShell, use the same commands if Git is installed.

## 2. Create Local Environment Files

Copy the example files:

```bash
cp .env.example .env
cp CloudBackend/.env.example CloudBackend/.env
cp SimulatedEdge/.env.example SimulatedEdge/.env
cp ControlBoard/.env.example ControlBoard/.env
cp "Digital Twin/.env.example" "Digital Twin/.env"
```

PowerShell version:

```powershell
Copy-Item .env.example .env
Copy-Item CloudBackend\.env.example CloudBackend\.env
Copy-Item SimulatedEdge\.env.example SimulatedEdge\.env
Copy-Item ControlBoard\.env.example ControlBoard\.env
Copy-Item "Digital Twin\.env.example" "Digital Twin\.env"
```

Open each copied `.env` file and replace every `change-me` or `your-...` value with your own values.

## 3. Create AWS IoT Credentials

In AWS IoT Core:

1. Create one thing/certificate set for each service you want to run:
   - cloud backend
   - simulated edge
   - control board
   - digital twin
2. Download each device certificate, private key, and Amazon Root CA 1.
3. Attach an IoT policy that allows connect, publish, subscribe, and receive for these topics:
   - `sensor/data`
   - `cloud/verdict`
   - `machine/signal`
4. Copy your AWS IoT endpoint into each service `.env`.

Put the downloaded files here, or change the paths in each `.env`:

```text
CloudBackend/CA/AmazonRootCA1.pem
CloudBackend/Certificates/cloud-certificate.pem.crt
CloudBackend/Keys/cloud-private.pem.key

SimulatedEdge/CA/AmazonRootCA1.pem
SimulatedEdge/Certificates/SimulatedMachine01-certificate.pem.crt
SimulatedEdge/Keys/SimulatedMachine01-private.pem.key

ControlBoard/Backend/Utils/CA/AmazonRootCA1.pem
ControlBoard/Backend/Utils/Certificates/controlboardbackend-certificate.pem.crt
ControlBoard/Backend/Utils/Keys/controlboardbackend-private.pem.key

Digital Twin/CA/AmazonRootCA1.pem
Digital Twin/Certificates/twinmodel-certificate.pem.crt
Digital Twin/Keys/twinmodel-private.pem.key
```

These real `.env`, `.pem`, `.key`, and `.crt` files are ignored by Git.

## 4. Configure InfluxDB

In the root `.env`, choose local values for:

```text
INFLUXDB_USERNAME
INFLUXDB_PASSWORD
INFLUXDB_ORG
INFLUXDB_BUCKET
INFLUXDB_TOKEN
```

Use the same InfluxDB values in `CloudBackend/.env`. The Docker setup creates InfluxDB using the root `.env`, and the cloud backend connects using `CloudBackend/.env`.

## 5. Run With Docker

From the repository root:

```bash
docker compose up --build
```

Open:

- Control board: [http://localhost:5000](http://localhost:5000)
- Digital twin: [http://localhost:8000/machine02](http://localhost:8000/machine02)
- InfluxDB: [http://localhost:8086](http://localhost:8086)

Default local dashboard users:

```text
admin / admin123
operator1 / operator123
operator2 / operator456
```

Change these before any real deployment.

## 6. Optional Firmware Setup

For ESP8266 hardware:

1. Copy `Firmware/Config.example.h` to `Firmware/Config.h`.
2. Put your Wi-Fi name/password, AWS IoT endpoint, device certificate, private key, and root CA in `Firmware/Config.h`.
3. Open `Firmware/EdgeDevice.ino` in Arduino IDE.
4. Install the required libraries from `Firmware/libraries` or through Arduino Library Manager.
5. Flash the board.

`Firmware/Config.h` is ignored by Git because it contains secrets.

## Running Services Without Docker

Install each service's Python dependencies first:

```bash
pip install -r CloudBackend/requirements.txt
pip install -r SimulatedEdge/requirements.txt
pip install -r ControlBoard/requirements.txt
pip install -r "Digital Twin/requirements.txt"
```

Then run services in separate terminals:

```bash
cd CloudBackend
python -m Cloud.App
```

```bash
cd SimulatedEdge
python -m App
```

```bash
cd ControlBoard
python init_db.py
python app.py
```

```bash
cd "Digital Twin"
uvicorn twin_backend:app --host 0.0.0.0 --port 8000
```