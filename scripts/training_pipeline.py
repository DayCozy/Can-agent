#!/usr/bin/env python3
"""
Training Pipeline – merged alle Sessions zu baseline.csv, trainiert Isolation Forest
"""
import csv, logging, sys, os
from pathlib import Path
import numpy as np

# Setup
sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger("pipeline")

FEATURE_ORDER = [
    "rpm", "coolant_temp", "oil_temp", "vehicle_speed", "throttle_position",
    "engine_load", "maf_rate", "lambda_voltage", "intake_air_temp", "fuel_pressure"
]

def merge_sessions():
    """Alle nicht-leeren CSV-Sessions zu einer baseline.csv zusammenführen"""
    logs_dir = Path("data/logs")
    out_path = Path("data/training/baseline.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows = []
    total_rows = 0
    sessions_used = 0

    for csv_file in sorted(logs_dir.glob("session_*.csv")):
        rows = list(csv.DictReader(open(csv_file)))
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

    log.info(f"Sessions: {sessions_used} | Roh: {total_rows} | Nach Dedupe: {len(all_rows)}")

    # Write merged (kein dedup nötig bei der Datenmenge)
    with open(out_path, "w", newline="") as f:
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
    """Isolation Forest trainieren"""
    from sklearn.ensemble import IsolationForest
    import joblib

    rows = list(csv.DictReader(open(baseline_path)))
    log.info(f"Training mit {len(rows)} Samples")

    # Fehlende Werte mit Median ersetzen (pro Spalte)
    data = {f: [] for f in FEATURE_ORDER}
    for r in rows:
        for f in FEATURE_ORDER:
            v = r.get(f, "")
            data[f].append(float(v) if v not in ("", None) else np.nan)

    # Median pro Feature
    medians = {f: float(np.nanmedian(v)) for f, v in data.items()}
    log.info(f"Mediane: {medians}")

    X = []
    for r in rows:
        row = []
        for f in FEATURE_ORDER:
            v = r.get(f, "")
            row.append(medians[f] if v in ("", None) else float(v))
        X.append(row)

    X = np.array(X)

    # Quick stats
    log.info(f"X shape: {X.shape}")
    log.info(f"RPM: {X[:,0].min():.0f} – {X[:,0].max():.0f}")
    log.info(f"Speed: {X[:,3].min():.0f} – {X[:,3].max():.0f}")
    log.info(f"Engine Load: {X[:,5].min():.0f} – {X[:,5].max():.0f}")

    # Trainieren
    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X)
    log.info("Modell trainiert!")

    # Score-Verteilung checken
    scores = model.score_samples(X)
    log.info(f"Score-Verteilung: min={scores.min():.4f}, mean={scores.mean():.4f}, max={scores.max():.4f}")

    # Save
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