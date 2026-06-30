#!/usr/bin/env python3
"""
Schreibt den aktuellen Fahrzeugkontext nach car_context.json
Wird vom Car-Agent bei jedem Loop-Tick aufgerufen (oder separat als Monitor)
"""

import json
from pathlib import Path

CONTEXT_FILE = Path(__file__).resolve().parent.parent / "car_context.json"


def update(data: dict, anomaly_score: float = None, engine_state: str = None, dtcs: list = None):
    """Aktuellen Kontext speichern."""
    ctx = {
        "data": data,
        "anomaly_score": anomaly_score,
        "engine_state": engine_state,
        "dtcs": dtcs if dtcs is not None else [],
    }

    tmp_file = CONTEXT_FILE.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(ctx, indent=2, default=str), encoding="utf-8")
    tmp_file.replace(CONTEXT_FILE)


def read():
    """Kontext laden (für Test/Debug)."""
    if CONTEXT_FILE.exists():
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    return None


if __name__ == "__main__":
    ctx = read()
    if ctx:
        print(json.dumps(ctx, indent=2, default=str))
    else:
        print("Kein Kontext vorhanden (Agent läuft nicht?)")