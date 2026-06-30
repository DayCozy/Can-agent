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

import numpy as np

from src.can_interface.obd_reader import OBDReader
from src.analytics.hardlimit_monitor import HardlimitMonitor
from src.analytics.anomaly_detector import AnomalyDetector
from src.analytics.engine_state import EngineStateMachine, EngineState
from src.alerts.telegram_alerts import TelegramAlerts
from src.data_logger.logger import DataLogger
from src.context.car_context import update as update_context


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("can-agent")


# Tick-Intervalle (bei 0.2 s/Tick)
DTC_INTERVAL_TICKS    = 150   # 30 s
REPORT_INTERVAL_TICKS = 300   # 60 s
MAX_CONSECUTIVE_FAILS = 10    # Reconnect nach N aufeinanderfolgenden Fehlern

# IPC-Kommandodatei (Telegram-Bot schreibt hier rein)
COMMAND_FILE = Path("data") / "commands.json"

_STATE_EMOJI = {
    EngineState.OFF:      "🔴",
    EngineState.STARTING: "🟡",
    EngineState.ON:       "🟢",
}


# ===========================================================================
# Mock OBD Reader
# ===========================================================================

class MockOBDReader:
    def __init__(self, config):
        self.config = config
        self._start_time = time.time()
        self.poll_interval = config.get("poll_interval_ms", 200) / 1000.0
        np.random.seed(42)

    def connect(self):
        pass

    def disconnect(self):
        pass

    def read_dtcs(self):
        return []

    def clear_dtcs(self):
        log.info("[MOCK] DTCs gelöscht")
        return True

    def read_all_pids(self):
        t = time.time() - self._start_time

        rpm             = 750 + 1500 * (0.5 + 0.5 * np.sin(t / 10))
        speed           = 0.0
        if rpm > 1000:
            speed       = min(60, (rpm - 1000) * 0.1)

        coolant_temp    = 75 + 10 * np.sin(t / 30)
        intake_air_temp = 20 + 5  * np.sin(t / 20)
        throttle        = max(0, min(100, (rpm - 750) / 20))
        engine_load     = max(0, min(100, (rpm - 750) / 25))
        maf_rate        = max(0, (engine_load / 100) * 10)
        lambda_voltage  = 0.45 + 0.1 * np.sin(t / 5)
        timing_advance  = max(0, min(50, (rpm - 750) / 30))
        fuel_pressure   = 300
        battery_voltage = 12.6 + 0.2 * np.sin(t / 10)
        oil_temp        = coolant_temp + 5
        fuel_level      = max(10, 90 - t / 200)
        runtime         = int(t)

        def noise(x, pc=0.02):
            return x * (1 + (np.random.rand() - 0.5) * 2 * pc)

        return {
            "rpm":               noise(rpm,             0.03),
            "coolant_temp":      noise(coolant_temp,    0.01),
            "oil_temp":          noise(oil_temp,        0.01),
            "vehicle_speed":     noise(speed,           0.05),
            "throttle_position": noise(throttle,        0.10),
            "engine_load":       noise(engine_load,     0.05),
            "maf_rate":          noise(maf_rate,        0.10),
            "lambda_voltage":    noise(lambda_voltage,  0.02),
            "intake_air_temp":   noise(intake_air_temp, 0.02),
            "fuel_pressure":     noise(fuel_pressure,   0.02),
            "battery_voltage":   noise(battery_voltage, 0.01),
            "fuel_level":        noise(fuel_level,      0.01),
            "runtime":           runtime,
            "timing_advance":    noise(timing_advance,  0.05),
        }


# ===========================================================================
# CAN-Agent
# ===========================================================================

class CANAgent:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.running    = False
        self.start_time = None

        self.hardlimits = self._load_json("hardlimits.json")
        self.obd_config = self._load_json("obd_pids.json")

        if os.getenv("USE_MOCK_OBD"):
            self.obd = MockOBDReader(self.obd_config)
            log.info("Using MOCK OBD reader")
        else:
            self.obd = OBDReader(self.obd_config)
            log.info("Using real OBD reader")

        self.hardlimit    = HardlimitMonitor(self.hardlimits)
        self.anomaly      = AnomalyDetector(str(Path("models") / "isolation_forest.joblib"))
        self.telegram     = TelegramAlerts(str(self.config_dir / "telegram.json"))
        self.logger       = DataLogger(str(Path("data") / "logs"))
        self.engine_state = EngineStateMachine()

        # DTC-Zustand: zuletzt gemeldete Codes, damit keine Duplikat-Alerts
        self._last_dtc_codes: set[str] = set()

        log.info("CAN-Agent initialisiert")

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _load_json(self, filename: str) -> dict:
        path = self.config_dir / filename
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"Konfigurationsdatei fehlt: {path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ungültige JSON-Konfiguration in {path}: {e}")

    @staticmethod
    def _f(val) -> str:
        if val is None:
            return "N/A"
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return str(val)

    def _reconnect(self):
        log.warning("Versuche OBD-Reconnect...")
        try:
            self.obd.disconnect()
        except Exception:
            pass
        try:
            self.obd.connect()
            log.info("OBD-Reconnect erfolgreich")
        except Exception as e:
            log.error(f"OBD-Reconnect fehlgeschlagen: {e}")

    def _process_commands(self):
        """
        Prüft ob der Telegram-Bot einen IPC-Befehl in COMMAND_FILE hinterlegt hat
        und führt ihn aus. Die Datei wird sofort nach dem Lesen gelöscht,
        damit kein Befehl doppelt ausgeführt wird.
        """
        if not COMMAND_FILE.exists():
            return

        try:
            command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
            COMMAND_FILE.unlink()  # Sofort löschen – vor der Ausführung
        except Exception as e:
            log.warning(f"IPC-Datei konnte nicht gelesen werden: {e}")
            try:
                COMMAND_FILE.unlink()
            except Exception:
                pass
            return

        action = command.get("action")
        log.info(f"IPC-Befehl empfangen: {action!r}")

        if action == "clear_dtc":
            success = self.obd.clear_dtcs()
            if success:
                self._last_dtc_codes.clear()  # Interne DTC-Zustandsliste zurücksetzen
                log.info("DTCs per IPC-Befehl erfolgreich gelöscht")
                self.telegram.send("✅ Fehlerspeicher wurde erfolgreich geleert.")
            else:
                log.warning("DTC-Löschen per IPC fehlgeschlagen")
                self.telegram.send("❌ Fehlerspeicher konnte nicht geleert werden.")

        elif action == "status":
            # Sofortiger Status-Report auf Anfrage
            log.info("Sofort-Statusreport angefordert")
            self.telegram.send("⏳ Status-Report wird beim nächsten Tick gesendet.")

        elif action == "read_dtc":
            # DTCs manuell auslesen
            dtcs = self.obd.read_dtcs()
            if dtcs:
                lines = ["🔍 Aktive DTCs:"]
                for d in dtcs:
                    severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                        d.get("severity", "info"), "⚪"
                    )
                    lines.append(
                        f"{severity_emoji} {d['code']}: {d['description']}\n"
                        f"   Ursachen: {', '.join(d.get('typical_causes', []))}"
                    )
                self.telegram.send("\n".join(lines))
            else:
                self.telegram.send("✅ Kein Fehlercode im Speicher.")

        else:
            log.warning(f"Unbekannter IPC-Befehl: {action!r}")

    def _handle_dtcs(self, dtcs: list):
        """
        Verarbeitet gelesene DTCs und sendet Telegram-Alerts nur für neue Codes.
        Löst bei kritischen Codes eine separate Warnung aus.
        """
        if not dtcs:
            if self._last_dtc_codes:
                # Alle vorherigen Codes verschwunden (z.B. nach clear)
                self._last_dtc_codes.clear()
            return

        current_codes = {d["code"] for d in dtcs}
        new_codes     = current_codes - self._last_dtc_codes

        if not new_codes:
            return  # Keine neuen Codes seit letztem Check

        self._last_dtc_codes = current_codes

        for dtc in dtcs:
            if dtc["code"] not in new_codes:
                continue

            severity       = dtc.get("severity", "info")
            severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
            causes         = "\n   • ".join(dtc.get("typical_causes", ["Keine Angabe"]))

            message = (
                f"{severity_emoji} *Neuer Fehlercode: {dtc['code']}*\n"
                f"📋 {dtc['description']}\n"
                f"📂 Kategorie: {dtc.get('category', 'Unbekannt')}\n"
                f"🔧 Mögliche Ursachen:\n   • {causes}"
            )
            self.telegram.send(message)
            log.warning(f"Neuer DTC: {dtc['code']} – {dtc['description']}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.running    = True
        self.start_time = datetime.now()
        log.info("CAN-Agent gestartet")
        self.telegram.send("🚗 CAN-Agent aktiv. Überwachung läuft.")
        self.obd.connect()

        try:
            self.loop()
        except KeyboardInterrupt:
            log.info("Beende durch Benutzer...")
        except Exception:
            log.exception("Unerwarteter Fehler")
        finally:
            self.stop()

    def loop(self):
        tick                 = 0
        consecutive_failures = 0

        while self.running:
            # IPC: Befehle vom Telegram-Bot verarbeiten
            self._process_commands()

            data = self.obd.read_all_pids()

            if not data:
                consecutive_failures += 1
                log.warning(
                    f"Keine PID-Daten empfangen – überspringe Tick "
                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILS})"
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILS:
                    log.error("Zu viele Fehlschläge – versuche Reconnect")
                    self._reconnect()
                    consecutive_failures = 0
                time.sleep(0.5)
                continue

            consecutive_failures = 0
            timestamp            = datetime.now()

            engine_state: EngineState | None = self.engine_state.update(data)
            anomaly_score                    = self.anomaly.predict(data)

            # DTCs periodisch abfragen + neue Codes mit Alert melden
            dtcs = []
            if tick % DTC_INTERVAL_TICKS == 0 and tick > 0:
                dtcs = self.obd.read_dtcs()
                if dtcs:
                    log.info(f"{len(dtcs)} DTC(s) gelesen: {[d['code'] for d in dtcs]}")
                self._handle_dtcs(dtcs)

            update_context(
                data,
                anomaly_score,
                engine_state.value if engine_state is not None else None,
                dtcs,
            )

            self.logger.log(timestamp, data, anomaly_score, engine_state)
            hardlimit_alerts = self.hardlimit.check(data, engine_state)

            if hardlimit_alerts:
                for alert in hardlimit_alerts:
                    self.telegram.send_alert(alert)

            if tick % REPORT_INTERVAL_TICKS == 0 and tick > 0:
                self.report(timestamp, data, hardlimit_alerts, anomaly_score, engine_state, dtcs)

            tick += 1
            time.sleep(self.obd.poll_interval)

    def report(
        self,
        ts: datetime,
        data: dict,
        alerts: list,
        anomaly_score,
        engine_state: EngineState | None,
        dtcs: list | None = None,
    ):
        uptime      = (ts - self.start_time).total_seconds()
        state_emoji = _STATE_EMOJI.get(engine_state, "⚪")
        state_label = engine_state.value.upper() if engine_state is not None else "UNKNOWN"

        lines = [
            "📊 STATUS-REPORT",
            f"Uptime:       {uptime / 60:.1f} min",
            f"{state_emoji} Engine:  {state_label}",
            f"RPM:          {self._f(data.get('rpm'))}",
            f"Speed:        {self._f(data.get('vehicle_speed'))} km/h",
            f"Coolant:      {self._f(data.get('coolant_temp'))}°C",
            f"Intake Air:   {self._f(data.get('intake_air_temp'))}°C",
            f"Oil Temp:     {self._f(data.get('oil_temp'))}°C",
            f"Throttle:     {self._f(data.get('throttle_position'))}%",
            f"Load:         {self._f(data.get('engine_load'))}%",
            f"MAF:          {self._f(data.get('maf_rate'))} g/s",
            f"Fuel:         {self._f(data.get('fuel_level'))}%",
            f"Voltage:      {self._f(data.get('battery_voltage'))} V",
            f"Runtime:      {self._f(data.get('runtime'))} s",
            f"Timing:       {self._f(data.get('timing_advance'))}°",
            f"Anomaly:      {self._f(anomaly_score)}",
            f"Alarms:       {len(alerts)}",
        ]

        # DTCs im Report anzeigen
        if dtcs:
            lines.append(f"⚠️ DTCs ({len(dtcs)}):")
            for d in dtcs:
                severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    d.get("severity", "info"), "⚪"
                )
                lines.append(f"  {severity_emoji} {d['code']}: {d['description']}")
        else:
            lines.append("✅ DTCs: keine")

        self.telegram.send("\n".join(lines))

    def stop(self):
        self.running = False

        for label, action in [
            ("OBD disconnect", self.obd.disconnect),
            ("Logger close",   self.logger.close),
        ]:
            try:
                action()
            except Exception as e:
                log.warning(f"Fehler beim Beenden ({label}): {e}")

        try:
            self.telegram.send("🔴 CAN-Agent gestoppt.")
        except Exception:
            pass

        log.info("CAN-Agent beendet")


if __name__ == "__main__":
    agent = CANAgent()
    agent.start()