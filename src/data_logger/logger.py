"""
Data Logger – speichert alle Sensordaten in SQLite + CSV
Nur沉睡-Commit alle 20 Rows (batch_size) statt nach jeder Zeile.
"""

import csv
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

log = logging.getLogger("logger")


class DataLogger:
    DB_ROWS_PER_COMMIT = 20
    CSV_ROWS_PER_FLUSH = 50

    DB_SCHEMA = """
        CREATE TABLE IF NOT EXISTS sensor_data (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            rpm         REAL,
            coolant_temp    REAL,
            oil_temp        REAL,
            vehicle_speed   REAL,
            throttle_position REAL,
            engine_load     REAL,
            maf_rate        REAL,
            lambda_voltage  REAL,
            intake_air_temp REAL,
            fuel_pressure   REAL,
            anomaly_score   REAL,
            engine_state    TEXT
        )
    """

    FIELDNAMES = [
        "timestamp", "rpm", "coolant_temp", "oil_temp", "vehicle_speed",
        "throttle_position", "engine_load", "maf_rate", "lambda_voltage",
        "intake_air_temp", "fuel_pressure", "anomaly_score", "engine_state"
    ]

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.log_dir / "can_data.db"
        self.csv_path = self.log_dir / f"session_{datetime.now():%Y%m%d_%H%M%S}.csv"

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

        self.csv_file = open(self.csv_path, "w", newline="")
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=self.FIELDNAMES)
        self.csv_writer.writeheader()

        # Batch-Zähler
        self._pending_db_rows = 0
        self._pending_csv_rows = 0

    def _init_db(self):
        self.conn.execute(self.DB_SCHEMA)
        self.conn.commit()

    def _build_row(self, timestamp: datetime, data: dict,
                   anomaly_score: Optional[float],
                   engine_state) -> dict:
        return {
            "timestamp":       timestamp.isoformat(),
            "rpm":             data.get("rpm"),
            "coolant_temp":    data.get("coolant_temp"),
            "oil_temp":        data.get("oil_temp"),
            "vehicle_speed":   data.get("vehicle_speed"),
            "throttle_position": data.get("throttle_position"),
            "engine_load":     data.get("engine_load"),
            "maf_rate":        data.get("maf_rate"),
            "lambda_voltage":  data.get("lambda_voltage"),
            "intake_air_temp": data.get("intake_air_temp"),
            "fuel_pressure":  data.get("fuel_pressure"),
            "anomaly_score":   anomaly_score,
            "engine_state":    engine_state.value if engine_state else None,
        }

    def _db_insert(self, row: dict):
        cols = list(row.keys())
        vals = list(row.values())
        placeholders = ",".join(["?"] * len(cols))
        self.conn.execute(
            f"INSERT INTO sensor_data ({','.join(cols)}) VALUES ({placeholders})",
            vals
        )
        self._pending_db_rows += 1

        if self._pending_db_rows >= self.DB_ROWS_PER_COMMIT:
            self.conn.commit()
            self._pending_db_rows = 0

    def _csv_write(self, row: dict):
        self.csv_writer.writerow(row)
        self._pending_csv_rows += 1

        if self._pending_csv_rows >= self.CSV_ROWS_PER_FLUSH:
            self.csv_file.flush()
            self._pending_csv_rows = 0

    def log(self, timestamp: datetime, data: dict,
            anomaly_score: float = None, engine_state=None):
        row = self._build_row(timestamp, data, anomaly_score, engine_state)
        self._db_insert(row)
        self._csv_write(row)

    def close(self):
        # Flush remaining pending rows
        if self._pending_db_rows > 0:
            self.conn.commit()
        if self._pending_csv_rows > 0:
            self.csv_file.flush()

        self.conn.close()
        self.csv_file.close()
        log.info(f"Data Logger geschlossen – CSV: {self.csv_path}")