import os
import json
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from joblib import dump

from AI.feature_engineering import build_features, FEATURE_COLUMNS
from AI.runtime_context import RUNNING, filter_running_rows

load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")
MEASUREMENT = os.getenv("AI_MEASUREMENT", "machine_metrics")

TRAIN_RANGE = os.getenv("AI_TRAIN_RANGE", "-6h")
MODEL_PATH = os.getenv("AI_MODEL_PATH", "AI/models/iforest.joblib")
META_PATH = os.getenv("AI_META_PATH", "AI/models/iforest.meta.json")

ROLL_WINDOW = int(os.getenv("AI_FEAT_ROLL_WINDOW", "12"))
EWM_SPAN = int(os.getenv("AI_FEAT_EWM_SPAN", "12"))

# IsolationForest hyperparams
N_ESTIMATORS = int(os.getenv("AI_IF_N_ESTIMATORS", "300"))
CONTAMINATION = float(os.getenv("AI_IF_CONTAMINATION", "0.03"))
RANDOM_STATE = int(os.getenv("AI_IF_RANDOM_STATE", "42"))
CRITICAL_TEMP = float(os.getenv("AI_CRITICAL_TEMP", "55"))
CRITICAL_VIB = float(os.getenv("AI_CRITICAL_VIB", "0.40"))
CRITICAL_CURR = float(os.getenv("AI_CRITICAL_CURR", "5.8"))
MIN_OPERATING_CURRENT = float(os.getenv("AI_MIN_OPERATING_CURRENT", "0.2"))

# Calibration resolution: 0..100 percentiles
CALIB_PCTS = np.arange(0, 101, dtype=float)

def _get_client() -> InfluxDBClient:
    if not (INFLUXDB_URL and INFLUXDB_TOKEN and INFLUXDB_ORG):
        raise RuntimeError("Missing InfluxDB env vars.")
    return InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)

def _query_training_data(machine_id: str | None = None) -> pd.DataFrame:
    client = _get_client()
    query_api = client.query_api()

    mid_filter = ""
    if machine_id:
        mid_filter = f'|> filter(fn: (r) => r.machine_id == "{machine_id}")'

    flux = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: {TRAIN_RANGE})
  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
  {mid_filter}
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
    return filter_running_rows(df)

def _select_training_baseline(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    numeric = df.copy()
    numeric["temperature"] = numeric["temperature"].astype(float)
    numeric["vibration"] = numeric["vibration"].astype(float)
    numeric["current"] = numeric["current"].astype(float)

    mask = (
        (numeric["temperature"] < CRITICAL_TEMP)
        & (numeric["vibration"] < CRITICAL_VIB)
        & (numeric["current"] < CRITICAL_CURR)
        & (numeric["current"] >= MIN_OPERATING_CURRENT)
    )

    filtered = numeric.loc[mask].reset_index(drop=True)
    if len(filtered) >= 50:
        return filtered
    return numeric.reset_index(drop=True)

def main():
    machine_id = os.getenv("AI_TRAIN_MACHINE_ID")  # optional; if empty train on all
    raw_df = _query_training_data(machine_id)
    df = _select_training_baseline(raw_df)

    if df.empty or len(df) < 50:
        raise RuntimeError(
            f"Not enough training data in Influx for range {TRAIN_RANGE}. "
            f"Got rows={len(df)}. Increase AI_TRAIN_RANGE or run the simulator longer."
        )

    feats = build_features(df, roll_window=ROLL_WINDOW, ewm_span=EWM_SPAN)
    X = feats[FEATURE_COLUMNS].values.astype(float)

    # Scale features (important for IF stability across features)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(Xs)

    # --- Calibration: empirical distribution of "normality scores" on training data ---
    train_scores = model.decision_function(Xs).astype(float)  # higher => more normal
    score_quantiles = np.percentile(train_scores, CALIB_PCTS)

    bundle = {
        "scaler": scaler,
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "feat_params": {"roll_window": ROLL_WINDOW, "ewm_span": EWM_SPAN},
        "train_range": TRAIN_RANGE,
        "calibration": {
            "percentiles": CALIB_PCTS,
            "score_quantiles": score_quantiles,
            "score_min": float(np.min(train_scores)),
            "score_max": float(np.max(train_scores)),
            "score_mean": float(np.mean(train_scores)),
            "score_std": float(np.std(train_scores) + 1e-9),
        },
    }

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    dump(bundle, MODEL_PATH)

    meta = {
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "train_range": TRAIN_RANGE,
        "measurement": MEASUREMENT,
        "bucket": INFLUXDB_BUCKET,
        "features": FEATURE_COLUMNS,
        "roll_window": ROLL_WINDOW,
        "ewm_span": EWM_SPAN,
        "iforest": {
            "n_estimators": N_ESTIMATORS,
            "contamination": CONTAMINATION,
            "random_state": RANDOM_STATE,
        },
        "rows_available": int(len(raw_df)),
        "rows_used": int(len(df)),
        "sessions_used": int(df["run_session_id"].nunique()) if "run_session_id" in df.columns else 1,
        "baseline_filter": {
            "operating_state": RUNNING,
            "critical_temp": CRITICAL_TEMP,
            "critical_vibration": CRITICAL_VIB,
            "critical_current": CRITICAL_CURR,
            "min_operating_current": MIN_OPERATING_CURRENT,
        },
    }
    with open(META_PATH, "w", encoding="utf-8") as meta_file:
        json.dump(meta, meta_file, indent=2)

    print(f"[OK] Trained IF model and saved to {MODEL_PATH}")
    print(f"[OK] Saved metadata to {META_PATH}")
    print(f"[CAL] decision_function score range: {bundle['calibration']['score_min']:.6f} .. {bundle['calibration']['score_max']:.6f}")
    print(f"[CAL] mean={bundle['calibration']['score_mean']:.6f}, std={bundle['calibration']['score_std']:.6f}")
    print(f"[CAL] p01={score_quantiles[1]:.6f}, p05={score_quantiles[5]:.6f}, p50={score_quantiles[50]:.6f}, p95={score_quantiles[95]:.6f}")

if __name__ == "__main__":
    main()
