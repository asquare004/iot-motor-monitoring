import os
from typing import Dict


class ProtectionController:
    def __init__(self):
        self._required_consecutive_anomalies = int(
            os.getenv("AI_CONSECUTIVE_ANOMALIES", "2")
        )
        self._machine_state: Dict[str, Dict[str, int | bool]] = {}

    def apply(self, sensor_data: Dict, verdict: Dict) -> Dict:
        machine_id = sensor_data.get("machine_id", "UNKNOWN")
        operating_state = verdict.get("operating_state", "UNKNOWN")
        run_session_id = int(verdict.get("run_session_id", 0) or 0)

        state = self._machine_state.setdefault(
            machine_id,
            {
                "run_session_id": run_session_id,
                "anomaly_streak": 0,
                "stop_latched": False,
            },
        )

        if state["run_session_id"] != run_session_id:
            state["run_session_id"] = run_session_id
            state["anomaly_streak"] = 0
            state["stop_latched"] = False

        if operating_state != "RUNNING":
            state["anomaly_streak"] = 0
            if operating_state == "OFF":
                state["stop_latched"] = False

            verdict["anomaly_streak"] = 0
            verdict["required_anomaly_streak"] = self._required_consecutive_anomalies
            verdict["pending_stop_confirmation"] = False
            verdict["stopping_required"] = False
            return verdict

        verdict["required_anomaly_streak"] = self._required_consecutive_anomalies

        if state["stop_latched"]:
            verdict["anomaly_streak"] = state["anomaly_streak"]
            verdict["pending_stop_confirmation"] = False
            verdict["stopping_required"] = False
            verdict["stop_latched"] = True
            return verdict

        hard_stop_required = bool(verdict.get("hard_stop_required", False))
        anomaly_candidate = bool(verdict.get("anomaly_candidate", False))

        if hard_stop_required:
            state["anomaly_streak"] = self._required_consecutive_anomalies
            state["stop_latched"] = True
            verdict["anomaly_streak"] = state["anomaly_streak"]
            verdict["pending_stop_confirmation"] = False
            verdict["stopping_required"] = True
            return verdict

        if anomaly_candidate:
            state["anomaly_streak"] += 1
        else:
            state["anomaly_streak"] = 0

        verdict["anomaly_streak"] = state["anomaly_streak"]
        verdict["pending_stop_confirmation"] = (
            0 < state["anomaly_streak"] < self._required_consecutive_anomalies
        )

        if state["anomaly_streak"] >= self._required_consecutive_anomalies:
            state["stop_latched"] = True
            verdict["stopping_required"] = True
        else:
            verdict["stopping_required"] = False

        return verdict
