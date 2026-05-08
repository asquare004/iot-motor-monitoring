from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    import pandas as pd

OFF = "OFF"
IDLE = "IDLE"
STARTING = "STARTING"
RUNNING = "RUNNING"
KNOWN_OPERATING_STATES = {OFF, IDLE, STARTING, RUNNING}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_sensor_context(sensor_data: Dict[str, Any], min_operating_current: float) -> Dict[str, Any]:
    switch_state = str(sensor_data.get("switch_state", "unknown")).upper()
    current = float(sensor_data.get("current", 0.0))

    operating_state = str(sensor_data.get("operating_state", "")).upper()
    if operating_state not in KNOWN_OPERATING_STATES:
        if switch_state != "ON":
            operating_state = OFF
        elif current < min_operating_current:
            operating_state = STARTING
        else:
            operating_state = RUNNING

    if operating_state == OFF:
        ml_eligible = False
    elif operating_state == RUNNING:
        ml_eligible = True
    else:
        ml_eligible = False

    return {
        "switch_state": switch_state,
        "operating_state": operating_state,
        "run_session_id": _safe_int(sensor_data.get("run_session_id"), 0),
        "state_sample_index": max(_safe_int(sensor_data.get("state_sample_index"), 0), 0),
        "ml_eligible": ml_eligible,
        "control_source": str(sensor_data.get("control_source", "UNKNOWN")).upper(),
    }


def filter_running_rows(df: "pd.DataFrame", run_session_id: Optional[int] = None) -> "pd.DataFrame":
    import pandas as pd

    if df.empty:
        return df

    filtered = df.copy()
    if "operating_state" in filtered.columns:
        filtered = filtered[filtered["operating_state"].astype(str).str.upper() == RUNNING]

    if run_session_id is not None and "run_session_id" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["run_session_id"], errors="coerce") == run_session_id]

    return filtered.sort_values("_time").reset_index(drop=True)
