import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

TWIN_URL = os.getenv("TWIN_URL")  # ex: http://twin_backend:8000/twin/update


def push_to_twin(sensor_data: Dict[str, Any], verdict: Optional[Dict[str, Any]] = None) -> None:
    if not TWIN_URL:
        return

    payload: Dict[str, Any] = dict(sensor_data)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    if verdict:
        payload.update(
            {
                "health_score": verdict.get("health"),
                "issues": verdict.get("issues"),
                "stopping_required": verdict.get("stopping_required"),
                "normal_score": verdict.get("normal_score"),
                "anomaly_prob": verdict.get("anomaly_prob"),
            }
        )
        payload["health"] = "ANOMALY" if verdict.get("stopping_required") else "HEALTHY"

    try:
        requests.post(TWIN_URL, json=payload, timeout=0.7)
    except Exception as e:
        print(f"[twin] push failed: {repr(e)}")