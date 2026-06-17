"""
Hardlimit-Monitor – prüft Schwellwerte und löst sofortige Alarme aus
"""

import logging
from typing import TypedDict

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

    def check(self, data: dict) -> list[HardlimitAlert]:
        alerts = []
        for param, cfg in self.limits.items():
            val = data.get(param)
            if val is None:
                continue

            lo = cfg["min"]
            hi = cfg["max"]
            unit = cfg["unit"]
            severity = cfg["severity"]

            if val < lo:
                alerts.append(HardlimitAlert(
                    parameter=param,
                    value=val,
                    limit_min=lo,
                    limit_max=hi,
                    unit=unit,
                    severity=severity
                ))
                log.warning(f"⚠️ {param} zu niedrig: {val:.2f}{unit} (min: {lo}{unit})")
            elif val > hi:
                alerts.append(HardlimitAlert(
                    parameter=param,
                    value=val,
                    limit_min=lo,
                    limit_max=hi,
                    unit=unit,
                    severity=severity
                ))
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
        else:
            return f"🚨 [{s.upper()}] {p}: {v:.2f}{u} (Maximum: {hi}{u})"