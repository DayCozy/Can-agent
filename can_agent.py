#!/usr/bin/env python3
"""
CAN-Agent – KI-gestütztes Fahrzeug-Monitoring
Main entry point
"""

import time
import json
import logging
from pathlib import Path
from datetime import datetime

from src.can_interface.obd_reader import OBDReader
from src.analytics.hardlimit_monitor import HardlimitMonitor
from src.analytics.anomaly_detector import AnomalyDetector
from src.alerts.telegram_alerts import TelegramAlerts
from src.data_logger.logger import DataLogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger("can-agent")

class CANAgent:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.running = False
        self.start_time = None

        # Load configs
        with open(self.config_dir / "hardlimits.json") as f:
            self.hardlimits = json.load(f)
        with open(self.config_dir / "obd_pids.json") as f:
            self.obd_config = json.load(f)

        # Init components
        self.obd = OBDReader(self.obd_config)
        self.hardlimit = HardlimitMonitor(self.hardlimits)
        self.anomaly = AnomalyDetector(str(Path("models") / "isolation_forest.joblib"))
        self.telegram = TelegramAlerts(str(Path(config_dir) / "telegram.json"))
        self.logger = DataLogger(str(Path("data") / "logs"))

        log.info("CAN-Agent initialisiert")

    def start(self):
        self.running = True
        self.start_time = datetime.now()
        log.info("CAN-Agent gestartet")
        self.telegram.send("🚗 CAN-Agent aktiv. Überwachung läuft.")

        self.obd.connect()

        try:
            self.loop()
        except KeyboardInterrupt:
            log.info("Beende durch Benutzer...")
            self.stop()

    def loop(self):
        tick = 0
        while self.running:
            data = self.obd.read_all_pids()
            if not data:
                time.sleep(0.5)
                continue

            timestamp = datetime.now()
            self.logger.log(timestamp, data)

            # Hardlimit-Check (Sofort-Alarm)
            hardlimit_alerts = self.hardlimit.check(data)

            # Anomalie-Score (wenn Modell trainiert)
            anomaly_score = self.anomaly.predict(data)

            # Reporting alle 5 seconds (25 ticks a 200ms)
            if tick % 25 == 0 and tick > 0:
                self.report(timestamp, data, hardlimit_alerts, anomaly_score)

            # Sofort-Alarm bei Hardlimit-Verletzung
            if hardlimit_alerts:
                for alert in hardlimit_alerts:
                    self.telegram.send_alert(alert)

            tick += 1
            time.sleep(0.2)

    def report(self, ts, data, alerts, anomaly_score):
        uptime = (ts - self.start_time).total_seconds()
        msg = (
            f"📊 *Status-Report*\n"
            f"⏱ Uptime: {uptime/60:.1f}min\n"
            f"🖥 RPM: {data.get('rpm', 'N/A')}\n"
            f"🌡 Kühlmittel: {data.get('coolant_temp', 'N/A')}°C\n"
            f"⚡ Lambda: {data.get('lambda_voltage', 'N/A')}V\n"
            f"🌲 Anomalie-Score: {anomaly_score:.4f}\n"
            f"🚨 Alarme: {len(alerts)}"
        )
        self.telegram.send(msg)

    def stop(self):
        self.running = False
        self.obd.disconnect()
        self.logger.close()
        self.telegram.send("🔴 CAN-Agent gestoppt.")
        log.info("CAN-Agent beendet")

if __name__ == "__main__":
    agent = CANAgent()
    agent.start()