#!/usr/bin/env python3
"""
CAN-Agent – KI-gestütztes Fahrzeug-Monitoring
Main entry point
"""

import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Optional mock OBD reader
if os.getenv("USE_MOCK_OBD"):
    class MockOBDReader:
        def __init__(self, config):
            self.config = config
            self._start_time = time.time()
            self._cycle = 0.0

        def connect(self):
            pass

        def disconnect(self):
            pass

        def read_all_pids(self):
            # Simulate a driving cycle: idle -> accelerate -> cruise -> decelerate
            t = time.time() - self._start_time
            # Base values
            rpm = 750 + 1500 * (0.5 + 0.5 * np.sin(t / 10))  # 750-2250 RPM
            speed = 0.0
            if rpm > 1000:
                speed = min(60, (rpm - 1000) * 0.1)  # up to 60 km/h
            coolant_temp = 75 + 10 * np.sin(t / 30)  # 65-85°C
            intake_air_temp = 20 + 5 * np.sin(t / 20)
            throttle = max(0, min(100, (rpm - 750) / 20))  # rough throttle
            engine_load = max(0, min(100, (rpm - 750) / 25))
            maf_rate = max(0, (engine_load / 100) * 10)  # rough
            lambda_voltage = 0.45 + 0.1 * np.sin(t / 5)  # oscillate around stoich
            timing_advance = max(0, min(50, (rpm - 750) / 30))
            fuel_pressure = 300  # kPa constant
            battery_voltage = 12.6 + 0.2 * np.sin(t / 10)
            oil_temp = coolant_temp + 5
            fuel_level = max(10, 90 - t / 200)  # slowly decreasing
            runtime = int(t)

            # Add some noise
            def noise(x, pc=0.02):
                return x * (1 + (np.random.rand() - 0.5) * 2 * pc)

            return {
                "rpm": noise(rpm, 0.03),
                "coolant_temp": noise(coolant_temp, 0.01),
                "oil_temp": noise(oil_temp, 0.01),
                "vehicle_speed": noise(speed, 0.05),
                "throttle_position": noise(throttle, 0.1),
                "engine_load": noise(engine_load, 0.05),
                "maf_rate": noise(maf_rate, 0.1),
                "lambda_voltage": noise(lambda_voltage, 0.02),
                "intake_air_temp": noise(intake_air_temp, 0.02),
                "fuel_pressure": noise(fuel_pressure, 0.02),
                "battery_voltage": noise(battery_voltage, 0.01),
                "fuel_level": noise(fuel_level, 0.01),
                "runtime": runtime,
                "timing_advance": noise(timing_advance, 0.05),
            }
else:
    from src.can_interface.obd_reader import OBDReader

from src.analytics.hardlimit_monitor import HardlimitMonitor
from src.analytics.anomaly_detector import AnomalyDetector
from src.analytics.engine_state import EngineStateMachine, EngineState
from src.alerts.telegram_alerts import TelegramAlerts
from src.data_logger.logger import DataLogger

from src.context.car_context import update as update_context

try:
    import numpy as np
except ImportError:
    # fallback if numpy not installed (should be in deps)
    class np:
        @staticmethod
        def sin(x):
            import math
            return math.sin(x)
        @staticmethod
        def rand():
            import random
            return random.random()

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

        with open(self.config_dir / "hardlimits.json") as f:
            self.hardlimits = json.load(f)
        with open(self.config_dir / "obd_pids.json") as f:
            self.obd_config = json.load(f)

        # Choose OBD reader: real or mock
        if os.getenv("USE_MOCK_OBD"):
            from src.can_interface.obd_reader import OBDReader  # still need the class for type? but we replaced
            self.obd = MockOBDReader(self.obd_config)
            log.info("Using MOCK OBD reader")
        else:
            self.obd = OBDReader(self.obd_config)
            log.info("Using real OBD reader")

        self.hardlimit = HardlimitMonitor(self.hardlimits)
        self.anomaly = AnomalyDetector(str(Path("models") / "isolation_forest.joblib"))
        self.telegram = TelegramAlerts(str(Path(config_dir) / "telegram.json"))
        self.logger = DataLogger(str(Path("data") / "logs"))
        self.engine_state = EngineStateMachine()

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

            # Engine State aktualisieren
            engine_state = self.engine_state.update(data)

            # Anomalie-Score (wenn Modell trainiert)
            anomaly_score = self.anomaly.predict(data)

            # Context-Datei für OpenClaw updaten
            update_context(data, anomaly_score, engine_state.value if engine_state else None)

            # Hardlimit-Check nur wenn Motor AN
            hardlimit_alerts = self.hardlimit.check(data, engine_state)

            # Reporting alle 25 Ticks (~5 Sekunden)
            if tick % 25 == 0 and tick > 0:
                self.report(timestamp, data, hardlimit_alerts, anomaly_score, engine_state)

            # Sofort-Alarm bei Hardlimit-Verletzung
            if hardlimit_alerts:
                for alert in hardlimit_alerts:
                    self.telegram.send_alert(alert)

            tick += 1
            time.sleep(0.2)

    def report(self, ts, data, alerts, anomaly_score, engine_state):
        uptime = (ts - self.start_time).total_seconds()
        # Get engine state emoji
        state_emoji = {
            EngineState.OFF: "🔴",
            EngineState.STARTING: "🟡",
            EngineState.ON: "🟢",
        }.get(engine_state, "⚪")
        # Build plain text message (no markdown to avoid parsing errors)
        lines = []
        lines.append("STATUS-REPORT")
        lines.append(f"Uptime: {uptime/60:.1f} min")
        lines.append(f"{state_emoji} Engine: {engine_state.value.upper()}")
        lines.append(f"RPM: {data.get('rpm', 'N/A')}")
        lines.append(f"Speed: {data.get('vehicle_speed', 'N/A')} km/h")
        lines.append(f"Coolant: {data.get('coolant_temp', 'N/A')}°C")
        lines.append(f"Intake Air: {data.get('intake_air_temp', 'N/A')}°C")
        lines.append(f"Throttle: {data.get('throttle_position', 'N/A')}%")
        lines.append(f"Load: {data.get('engine_load', 'N/A')}%")
        lines.append(f"MAF: {data.get('maf_rate', 'N/A')} g/s")
        lines.append(f"Fuel: {data.get('fuel_level', 'N/A')}%")
        lines.append(f"Voltage: {data.get('battery_voltage', 'N/A')} V")
        lines.append(f"Runtime: {data.get('runtime', 'N/A')} s")
        lines.append(f"Timing: {data.get('timing_advance', 'N/A')}°")
        lines.append(f"Anomaly Score: {anomaly_score:.4f}")
        lines.append(f"Alarms: {len(alerts)}")
        msg = "\n".join(lines)
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