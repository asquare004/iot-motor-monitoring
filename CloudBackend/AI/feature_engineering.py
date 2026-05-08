import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "temp", "vib", "curr",
    "dtemp", "dvib", "dcurr",
    "temp_roll_mean", "temp_roll_std",
    "vib_roll_mean", "vib_roll_std",
    "curr_roll_mean", "curr_roll_std",
    "temp_ewm", "vib_ewm", "curr_ewm",
    "temp_slope", "vib_slope", "curr_slope",
]

def _slope(series: pd.Series) -> float:
    """Simple slope via linear fit; robust enough for short windows."""
    y = series.values.astype(float)
    if len(y) < 3:
        return 0.0
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, y, 1)[0])

def _build_features_for_window(df: pd.DataFrame, roll_window: int = 12, ewm_span: int = 12) -> pd.DataFrame:
    """
    df must have columns: ["_time", "temperature", "vibration", "current"]
    Returns a feature dataframe aligned with df rows.
    """
    df = df.sort_values("_time").reset_index(drop=True)

    out = pd.DataFrame()
    out["temp"] = df["temperature"].astype(float)
    out["vib"] = df["vibration"].astype(float)
    out["curr"] = df["current"].astype(float)

    # First differences
    out["dtemp"] = out["temp"].diff().fillna(0.0)
    out["dvib"]  = out["vib"].diff().fillna(0.0)
    out["dcurr"] = out["curr"].diff().fillna(0.0)

    # Rolling stats 
    out["temp_roll_mean"] = (
        out["temp"].rolling(roll_window, min_periods=3).mean().bfill()
    )
    out["temp_roll_std"] = (
        out["temp"].rolling(roll_window, min_periods=3).std().fillna(0.0)
    )

    out["vib_roll_mean"] = (
        out["vib"].rolling(roll_window, min_periods=3).mean().bfill()
    )
    out["vib_roll_std"] = (
        out["vib"].rolling(roll_window, min_periods=3).std().fillna(0.0)
    )

    out["curr_roll_mean"] = (
        out["curr"].rolling(roll_window, min_periods=3).mean().bfill()
    )
    out["curr_roll_std"] = (
        out["curr"].rolling(roll_window, min_periods=3).std().fillna(0.0)
    )

    # EWMA (captures slow drift like bearing wear)
    out["temp_ewm"] = out["temp"].ewm(span=ewm_span, adjust=False).mean()
    out["vib_ewm"]  = out["vib"].ewm(span=ewm_span, adjust=False).mean()
    out["curr_ewm"] = out["curr"].ewm(span=ewm_span, adjust=False).mean()

    # Slopes over a rolling window (trend)
    temp_slope = []
    vib_slope = []
    curr_slope = []
    for i in range(len(out)):
        start = max(0, i - roll_window + 1)
        temp_slope.append(_slope(out["temp"].iloc[start:i+1]))
        vib_slope.append(_slope(out["vib"].iloc[start:i+1]))
        curr_slope.append(_slope(out["curr"].iloc[start:i+1]))

    out["temp_slope"] = temp_slope
    out["vib_slope"]  = vib_slope
    out["curr_slope"] = curr_slope

    # Ensure column order and numeric safety
    out = out[FEATURE_COLUMNS].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return out


def build_features(
    df: pd.DataFrame,
    roll_window: int = 12,
    ewm_span: int = 12,
    session_column: str = "run_session_id",
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    if session_column not in df.columns:
        return _build_features_for_window(df, roll_window=roll_window, ewm_span=ewm_span)

    features = []
    for _, group in df.groupby(session_column, sort=False):
        features.append(
            _build_features_for_window(group, roll_window=roll_window, ewm_span=ewm_span)
        )

    return pd.concat(features, ignore_index=True) if features else pd.DataFrame(columns=FEATURE_COLUMNS)
