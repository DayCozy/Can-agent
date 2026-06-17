"""
Data Logger – speichert alle Sensordaten in SQLite + CSV
"""

import csv
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("logger")

class DataLogger:
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.log_dir / "can_data.db"
        self.csv_path = self.log_dir / f"session_{datetime.now():%Y%m%d_%H%M%S}.csv"

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        self.csv_file = open(self.csv_path, "w", newline="")
        self.csv_writer = None

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                rpm REAL,
                coolant_temp REAL,
                oil_temp REAL,
                vehicle_speed REAL,
                throttle_position REAL,
                engine_load REAL,
                maf_rate REAL,
                lambda_voltage REAL,
                intake_air_temp REAL,
                fuel_pressure REAL,
                anomaly_score REAL
            )
        """)
        self.conn.commit()

    def log(self, timestamp: datetime, data: dict, anomaly_score: float = None):
        row = {
            "timestamp": timestamp.isoformat(),
            "rpm": data.get("rpm"),
            "coolant_temp": data.get("coolant_temp"),
            "oil_temp": data.get("oil_temp"),
            "vehicle_speed": data.get("vehicle_speed"),
            "throttle_position": data.get("throttle_position"),
            "engine_load": data.get("engine_load"),
            "maf_rate": data.get("maf_rate"),
            "lambda_voltage": data.get("lambda_voltage"),
            "intake_air_temp": data.get("intake_air_temp"),
            "fuel_pressure": data.get("fuel_pressure"),
            "anomaly_score": anomaly_score,
        }

        # SQLite
        cols = list(row.keys())
        vals = list(row.values())
        placeholders = ",".join(["?"] * len(cols))
        self.conn.execute(
            f"INSERT INTO sensor_data ({','.join(cols)}) VALUES ({placeholders})",
            vals
        )
        self.conn.commit()

        # CSV
        if self.csv_writer is None:
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=list(row.keys()))
            self.csv_writer.writeheader()
        self.csv_writer.writerow(row)
        self.csv_file.flush()

    def close(self):
        self.conn.close()
        self.csv_file.close()
        log.info(f"Data Logger geschlossen – CSV: {self.csv_path}")