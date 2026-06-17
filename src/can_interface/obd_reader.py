"""
OBD-2 / CAN Interface mit python-can
Liest OBD2-PIDs vom Fahrzeug-CAN-Bus
"""

import logging
import can

log = logging.getLogger("obd_reader")

class OBDReader:
    def __init__(self, config: dict):
        self.config = config
        self.bus = None
        self.poll_interval = config.get("poll_interval_ms", 200) / 1000.0

    def connect(self):
        try:
            self.bus = can.Bus(interface='socketcan', channel='can0', bitrate=500000)
            log.info("CAN-Verbindung hergestellt (can0, 500kbit/s)")
        except Exception as e:
            log.error(f"CAN-Verbindung fehlgeschlagen: {e}")
            raise

    def disconnect(self):
        if self.bus:
            self.bus.shutdown()
            log.info("CAN-Verbindung geschlossen")

    def read_pid(self, mode: int, pid: str) -> float | None:
        """Liest einen einzelnen OBD2-PID"""
        pid_int = int(pid, 16)
        msg = can.Message(
            arbitration_id=0x7DF,  # OBD2 Broadcast
            data=[0x02, mode, pid_int, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=False
        )
        try:
            self.bus.send(msg)
            response = self.bus.recv(timeout=1.0)
            if response and response.data[2] == pid_int:
                return self._parse_response(response.data, pid)
        except Exception:
            pass
        return None

    def read_all_pids(self) -> dict:
        """Liest alle konfigurierten PIDs"""
        data = {}
        for pid_cfg in self.config.get("pids", []):
            val = self.read_pid(pid_cfg["mode"], pid_cfg["pid"])
            if val is not None:
                data[pid_cfg["name"]] = val
        return data

    def _parse_response(self, raw: bytes, pid: str) -> float | None:
        """Parst OBD2-Rohdaten anhand der Formel"""
        formulas = {
            "0C": lambda d: ((d[3]*256)+d[4])/4,        # RPM
            "05": lambda d: d[3]-40,                      # Coolant
            "5C": lambda d: d[3]-40,                       # Oil Temp
            "0D": lambda d: d[3],                          # Speed
            "11": lambda d: d[3]*100/255,                  # Throttle
            "04": lambda d: d[3]*100/255,                  # Engine Load
            "0A": lambda d: d[3]*3,                        # Fuel Pressure
            "0E": lambda d: d[3]/2-64,                     # Timing Advance
            "0F": lambda d: d[3]-40,                      # IAT
            "10": lambda d: ((d[3]*256)+d[4])*0.01,       # MAF
            "1F": lambda d: (d[3]*256)+d[4],               # Runtime
            "2F": lambda d: d[3]*100/255,                  # Fuel Level
            "42": lambda d: ((d[3]*256)+d[4])/1000,        # Battery Voltage
            "14": lambda d: d[3]*0.005,                    # Lambda O2
        }
        fn = formulas.get(pid)
        return fn(raw) if fn else None