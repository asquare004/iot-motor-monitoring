import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from joblib import load

from AI.feature_engineering import build_features, FEATURE_COLUMNS
from AI.runtime_context import RUNNING, filter_running_rows, normalize_sensor_context

load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")
MEASUREMENT = os.getenv("AI_MEASUREMENT", "machine_metrics")

# Inference window
INFER_RANGE = os.getenv("AI_INFER_RANGE", "-10m")

# Model artifact
MODEL_PATH = os.getenv("AI_MODEL_PATH", "AI/models/iforest.joblib")

# Feature params (must match training)
ROLL_WINDOW = int(os.getenv("AI_FEAT_ROLL_WINDOW", "12"))
EWM_SPAN = int(os.getenv("AI_FEAT_EWM_SPAN", "12"))

# Decision thresholds in anomaly-probability space [0,1]
STOP_ANOMALY = float(os.getenv("AI_STOP_ANOMALY", "0.85"))
WARN_ANOMALY = float(os.getenv("AI_WARN_ANOMALY", "0.55"))

# Safety rails (still useful as “hard stops”)
CRITICAL_TEMP = float(os.getenv("AI_CRITICAL_TEMP", "55"))
CRITICAL_VIB = float(os.getenv("AI_CRITICAL_VIB", "0.40"))
CRITICAL_CURR = float(os.getenv("AI_CRITICAL_CURR", "5.8"))
MIN_OPERATING_CURRENT = float(os.getenv("AI_MIN_OPERATING_CURRENT", "0.2"))
MIN_RUNNING_HISTORY = int(os.getenv("AI_MIN_RUNNING_HISTORY", "5"))

_influx_client: Optional[InfluxDBClient] = None
_bundle = None  # {"scaler":..., "model":..., "calibration":...}

def _get_influx_client() -> InfluxDBClient:
    global _influx_client
    if _influx_client is None:
        if not (INFLUXDB_URL and INFLUXDB_TOKEN and INFLUXDB_ORG):
            raise RuntimeError("Missing InfluxDB env vars.")
        _influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    return _influx_client

def _load_model_bundle():
    global _bundle
    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(f"AI model not found at {MODEL_PATH}. Run: python -m AI.train_iforest")
        _bundle = load(MODEL_PATH)
    return _bundle

def _query_recent(machine_id: str, run_session_id: int) -> pd.DataFrame:
    client = _get_influx_client()
    query_api = client.query_api()

    flux = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: {INFER_RANGE})
  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
  |> filter(fn: (r) => r.machine_id == "{machine_id}")
  |> filter(fn: (r) => r.operating_state == "{RUNNING}")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "current" or r._field == "run_session_id")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "temperature", "vibration", "current", "run_session_id", "operating_state"])
"""
    frames = query_api.query_data_frame(flux, org=INFLUXDB_ORG)
    if isinstance(frames, list):
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        df = frames

    if df.empty:
        return df

    for c in ["result", "table"]:
        if c in df.columns:
            df = df.drop(columns=[c])

    df = df.dropna(subset=["temperature", "vibration", "current"])
    return filter_running_rows(df, run_session_id=run_session_id)

def _anomaly_probability_from_score(normal_score: float, calib: Dict) -> float:
    """
    Map IF decision_function score -> anomaly probability in [0,1]
    using empirical CDF derived from training scores.

    We store training score quantiles at percentiles 0..100.
    We approximate CDF(score) by interpolating between those quantiles.
    p_anom = 1 - CDF(score)
    """
    qs = np.array(calib["score_quantiles"], dtype=float)     # scores at p=0..100
    ps = np.array(calib["percentiles"], dtype=float) / 100.0 # 0..1

    # Interpolate: given score -> percentile.
    # np.interp expects x increasing; qs should be non-decreasing (percentile output is).
    cdf = float(np.interp(normal_score, qs, ps, left=0.0, right=1.0))
    p_anom = 1.0 - cdf
    return float(np.clip(p_anom, 0.0, 1.0))

def evaluate_sensor_data(sensor_data: Dict) -> Dict:
    context = normalize_sensor_context(sensor_data, MIN_OPERATING_CURRENT)
    machine_id = sensor_data.get("machine_id", "UNKNOWN")
    temp = float(sensor_data.get("temperature", 0.0))
    vib = float(sensor_data.get("vibration", 0.0))
    curr = float(sensor_data.get("current", 0.0))

    issues: List[str] = []

    if temp >= CRITICAL_TEMP:
        issues.append("OVERHEAT")
    if vib >= CRITICAL_VIB:
        issues.append("HIGH_VIBRATION")
    if curr >= CRITICAL_CURR:
        issues.append("CURRENT_SPIKE")

    hard_stop_required = "OVERHEAT" in issues or "CURRENT_SPIKE" in issues

    base_verdict = {
        "operating_state": context["operating_state"],
        "run_session_id": context["run_session_id"],
        "state_sample_index": context["state_sample_index"],
        "ml_eligible": context["ml_eligible"],
        "detection_active": False,
        "issues": issues,
        "normal_score": None,
        "anomaly_prob": None,
        "hard_stop_required": hard_stop_required,
        "anomaly_candidate": False,
        "stopping_required": False,
    }

    if context["operating_state"] != RUNNING:
        health_status = "OFF" if context["operating_state"] == "OFF" else context["operating_state"]
        health_score = 100.0 if context["operating_state"] == "OFF" else 85.0
        if hard_stop_required:
            health_status = "ANOMALY"
            health_score = 10.0
        return {
            **base_verdict,
            "health_score": round(health_score, 2),
            "health_status": health_status,
        }

    if context["state_sample_index"] < MIN_RUNNING_HISTORY:
        health_score = 85.0 if not hard_stop_required else 10.0
        return {
            **base_verdict,
            "health_score": round(health_score, 2),
            "health_status": "WARMUP" if not hard_stop_required else "ANOMALY",
        }

    # Load model bundle
    try:
        bundle = _load_model_bundle()
        scaler = bundle["scaler"]
        model = bundle["model"]
        calib = bundle.get("calibration")
        if calib is None:
            raise RuntimeError("Model bundle missing calibration. Re-train with updated trainer.")
    except Exception:
        health = 30.0 if hard_stop_required else 75.0
        return {
            **base_verdict,
            "health_score": round(health, 2),
            "health_status": "ANOMALY" if hard_stop_required else "MONITORING",
            "issues": issues + ["MODEL_UNAVAILABLE"],
        }

    try:
        df = _query_recent(machine_id, context["run_session_id"])
    except Exception:
        df = pd.DataFrame()

    if df.empty or len(df) < MIN_RUNNING_HISTORY - 1:
        health = 35.0 if hard_stop_required else 80.0
        return {
            **base_verdict,
            "health_score": round(health, 2),
            "health_status": "ANOMALY" if hard_stop_required else "WARMUP",
            "issues": issues + ["INSUFFICIENT_RUNNING_HISTORY"],
        }

    current_row = pd.DataFrame([{
        "_time": pd.Timestamp.utcnow(),
        "temperature": temp,
        "vibration": vib,
        "current": curr,
        "run_session_id": context["run_session_id"],
    }])
    df2 = pd.concat([df, current_row], ignore_index=True)

    feats = build_features(df2, roll_window=ROLL_WINDOW, ewm_span=EWM_SPAN)
    x = feats.iloc[-1][FEATURE_COLUMNS].values.astype(float).reshape(1, -1)
    xs = scaler.transform(x)

    normal_score = float(model.decision_function(xs)[0])

    anomaly = _anomaly_probability_from_score(normal_score, calib)
    health = 100.0 * (1.0 - anomaly)
    health = float(np.clip(health, 0.0, 100.0))

    if anomaly >= WARN_ANOMALY:
        issues.append("ML_ANOMALY")
    if anomaly >= STOP_ANOMALY:
        issues.append("ML_CRITICAL")

    anomaly_candidate = (
        anomaly >= STOP_ANOMALY
        or ("ML_ANOMALY" in issues and "HIGH_VIBRATION" in issues)
    )
    health_status = "ANOMALY" if hard_stop_required or anomaly >= WARN_ANOMALY else "HEALTHY"

    return {
        **base_verdict,
        "health_score": round(health, 2),
        "health_status": health_status,
        "issues": issues,
        "normal_score": round(normal_score, 6),
        "anomaly_prob": round(float(anomaly), 6),
        "hard_stop_required": hard_stop_required,
        "anomaly_candidate": anomaly_candidate,
        "detection_active": True,
    }
