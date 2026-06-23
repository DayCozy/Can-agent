#!/usr/bin/env python3
"""
Schreibt den aktuellen Fahrzeugkontext nach car_context.json
Wird vom Car-Agent bei jedem Loop-Tick aufgerufen (oder separat als Monitor)
"""
import json, sys
from pathlib import Path

CONTEXT_FILE = Path(__file__).parent.parent / "car_context.json"

def update(data: dict, anomaly_score: float = None, engine_state: str = None):
    """Aktuellen Kontext speichern"""
    ctx = {
        "data": data,
        "anomaly_score": anomaly_score,
        "engine_state": engine_state,
    }
    with open(CONTEXT_FILE, "w") as f:
        json.dump(ctx, f, indent=2, default=str)

def read():
    """Kontext laden (für Test/Debug)"""
    if CONTEXT_FILE.exists():
        return json.loads(CONTEXT_FILE.read_text())
    return None

if __name__ == "__main__":
    # CLI test
    ctx = read()
    if ctx:
        print(json.dumps(ctx, indent=2, default=str))
    else:
        print("Kein Kontext vorhanden (Agent läuft nicht?)")