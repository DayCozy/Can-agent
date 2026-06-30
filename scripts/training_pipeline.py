#!/usr/bin/env python3
"""
Training Pipeline – merged alle Sessions zu baseline.csv, trainiert Isolation Forest
"""

import csv
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline")

FEATURE_ORDER = [
    "rpm", "coolant_temp", "oil_temp", "vehicle_speed", "throttle_position",
    "engine_load", "maf_rate", "lambda_voltage", "intake_air_temp", "fuel_pressure"
]


def safe_float(value):
    try:
        if value in ("", None):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def merge_sessions():
    logs_dir = Path("data/logs")
    out_path = Path("data/training/baseline.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows = []
    total_rows = 0
    sessions_used = 0

    for csv_file in sorted(logs_dir.glob("session_*.csv")):
        with csv_file.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if len(rows) < 5:
            log.info(f"Überspringe {csv_file.name} (nur {len(rows)} Zeilen)")
            continue

        all_rows.extend(rows)
        total_rows += len(rows)
        sessions_used += 1
        log.info(f"  + {csv_file.name}: {len(rows)} Zeilen")

    if not all_rows:
        log.error("Keine brauchbaren Sessions gefunden!")
        return None

    log.info(f"Sessions: {sessions_used} | Roh: {total_rows} | Gesamt: {len(all_rows)}")

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp"] + FEATURE_ORDER)
        writer.writeheader()
        for r in all_rows:
            row = {"timestamp": r.get("timestamp", "")}
            for feat in FEATURE_ORDER:
                row[feat] = r.get(feat, "") or ""
            writer.writerow(row)

    log.info(f"Baseline gespeichert: {out_path}")
    return out_path


def train_model(baseline_path):
    from sklearn.ensemble import IsolationForest
    import joblib

    with open(baseline_path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info(f"Training mit {len(rows)} Samples")

    data = {f: [] for f in FEATURE_ORDER}
    for r in rows:
        for f in FEATURE_ORDER:
            data[f].append(safe_float(r.get(f, "")))

    medians = {}
    for f, vals in data.items():
        med = np.nanmedian(vals)
        medians[f] = float(med) if not np.isnan(med) else 0.0

    log.info(f"Mediane: {medians}")

    X = []
    valid_rows = 0
    for r in rows:
        row = []
        for f in FEATURE_ORDER:
            v = safe_float(r.get(f, ""))
            row.append(medians[f] if np.isnan(v) else v)
        X.append(row)
        valid_rows += 1

    X = np.array(X, dtype=float)

    log.info(f"X shape: {X.shape}")
    log.info(f"RPM: {X[:,0].min():.0f} – {X[:,0].max():.0f}")
    log.info(f"Speed: {X[:,3].min():.0f} – {X[:,3].max():.0f}")
    log.info(f"Engine Load: {X[:,5].min():.0f} – {X[:,5].max():.0f}")

    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X)
    log.info("Modell trainiert!")

    scores = model.score_samples(X)
    log.info(f"Score-Verteilung: min={scores.min():.4f}, mean={scores.mean():.4f}, max={scores.max():.4f}")

    out_path = Path("models/isolation_forest.joblib")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_path)
    log.info(f"Modell gespeichert: {out_path}")
    return out_path


if __name__ == "__main__":
    baseline = merge_sessions()
    if baseline:
        model_path = train_model(baseline)
        print(f"\n✅ FERTIG: {model_path}")
    else:
        print("\n❌ FEHLER: Keine Daten gefunden")
        sys.exit(1)