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

## Before Pushing To A New GitHub Repo

Do not push old Git history if it ever contained secrets. Create a new repo with a fresh first commit:

```bash
git init -b main
git add -A
git commit -m "Initial sanitized project"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

If this folder already has old Git history, copy it to a new folder first and remove `.git`:

```powershell
Copy-Item -Recurse . ..\iotproject-public
Remove-Item -Recurse -Force ..\iotproject-public\.git
cd ..\iotproject-public
git init -b main
git add -A
git commit -m "Initial sanitized project"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Before pushing, run:

```bash
git ls-files | rg "\.(env|pem|key|crt|p12|pfx|pyc|joblib)$|Config\.h$"
rg -n --hidden -g '!Firmware/libraries/**' -g '!**/.git/**' "PRIVATE KEY|SMTP_PASS=.+|AKIA|ASIA"
```

The first command should print nothing. The second command should not show real credentials.

If this project was ever committed with real credentials, rotate them:

- Recreate AWS IoT certificates and deactivate/delete the old ones.
- Revoke old email app passwords.
- Change old InfluxDB passwords/tokens.
- Change any exposed Wi-Fi password.
