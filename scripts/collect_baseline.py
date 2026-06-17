#!/usr/bin/env python3
"""
Collect Baseline Data – sammelt Fahrdaten für Isolation Forest Training
"""
import time
import json
import logging
from datetime import datetime
from pathlib import Path

from src.can_interface.obd_reader import OBDReader

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("collect")

def collect(duration_min: int = 30, output_path: str = "data/training/baseline.csv"):
    with open("config/obd_pids.json") as f:
        cfg = json.load(f)

    reader = OBDReader(cfg)
    reader.connect()

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import csv
    fieldnames = ["timestamp", "rpm", "coolant_temp", "oil_temp", "vehicle_speed",
                  "throttle_position", "engine_load", "maf_rate", "lambda_voltage",
                  "intake_air_temp", "fuel_pressure", "fuel_level", "battery_voltage"]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        end_time = time.time() + duration_min * 60
        count = 0

        log.info(f"Sammle Baseline-Daten für {duration_min} Minuten...")
        while time.time() < end_time:
            data = reader.read_all_pids()
            if data:
                row = {"timestamp": datetime.now().isoformat()}
                row.update(data)
                writer.writerow(row)
                count += 1
                if count % 50 == 0:
                    log.info(f"  {count} Samples gesammelt...")

            time.sleep(0.2)

    reader.disconnect()
    log.info(f"Fertig! {count} Samples in {out_path} gespeichert.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=30, help="Sammel-Dauer in Minuten")
    parser.add_argument("--output", default="data/training/baseline.csv")
    args = parser.parse_args()
    collect(args.minutes, args.output)