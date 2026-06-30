import logging
from typing import TypedDict
from src.analytics.engine_state import EngineState

log = logging.getLogger("hardlimit")

class HardlimitAlert(TypedDict):
    parameter: str
    value: float
    limit_min: float
    limit_max: float
    unit: str
    severity: str

class HardlimitMonitor:
    def __init__(self, limits: dict):
        self.limits = limits

    def check(self, data: dict, engine_state: EngineState) -> list[HardlimitAlert]:
        if engine_state != EngineState.ON:
            return []

        alerts: list[HardlimitAlert] = []
        for param, cfg in self.limits.items():
            val = data.get(param)
            if val is None:
                continue

            try:
                val = float(val)
                lo = float(cfg["min"])
                hi = float(cfg["max"])
            except (KeyError, TypeError, ValueError):
                log.warning(f"Ungültige Hardlimit-Config für {param}")
                continue

            unit = cfg.get("unit", "")
            severity = cfg.get("severity", "medium")

            if val < lo or val > hi:
                alert: HardlimitAlert = {
                    "parameter": param,
                    "value": val,
                    "limit_min": lo,
                    "limit_max": hi,
                    "unit": unit,
                    "severity": severity,
                }
                alerts.append(alert)

                if val < lo:
                    log.warning(f"⚠️ {param} zu niedrig: {val:.2f}{unit} (min: {lo}{unit})")
                else:
                    log.warning(f"⚠️ {param} zu hoch: {val:.2f}{unit} (max: {hi}{unit})")

        return alerts

    def format_alert(self, alert: HardlimitAlert) -> str:
        p = alert["parameter"]
        v = alert["value"]
        lo = alert["limit_min"]
        hi = alert["limit_max"]
        u = alert["unit"]
        s = alert["severity"]

        if v < lo:
            return f"🚨 [{s.upper()}] {p}: {v:.2f}{u} (Minimum: {lo}{u})"
        return f"🚨 [{s.upper()}] {p}: {v:.2f}{u} (Maximum: {hi}{u})"