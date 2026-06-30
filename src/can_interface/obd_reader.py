import socket
import logging
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


log = logging.getLogger("obd_reader")


PID_FORMULAS = {
    "0C": lambda A, B: ((A * 256) + B) / 4,        # rpm
    "05": lambda A, B: A - 40,                     # coolant temp
    "5C": lambda A, B: A - 40,                     # oil temp
    "0D": lambda A, B: A,                          # speed
    "11": lambda A, B: A * 100 / 255,              # throttle pos
    "04": lambda A, B: A * 100 / 255,              # engine load
    "0A": lambda A, B: A * 3,                      # fuel pressure
    "0E": lambda A, B: A / 2 - 64,                 # timing advance
    "0F": lambda A, B: A - 40,                     # intake temp
    "10": lambda A, B: ((A * 256) + B) * 0.01,     # maf
    "1F": lambda A, B: (A * 256) + B,              # runtime
    "2F": lambda A, B: A * 100 / 255,              # fuel level
    "42": lambda A, B: ((A * 256) + B) / 1000,     # control module voltage
    "14": lambda A, B: A * 0.005,                  # o2 / lambda voltage
}

# Anzahl der Gesamt-Bytes in der ECU-Antwort (inkl. Mode-Byte + PID-Byte)
# Beispiel "0C": "41 0C XX XX" -> 4 Bytes gesamt, davon 2 Datenbytes (A, B)
EXPECTED_BYTES = {
    "0C": 4,  # 2 Datenbytes
    "05": 3,  # 1 Datenbyte
    "5C": 3,
    "0D": 3,
    "11": 3,
    "04": 3,
    "0A": 3,
    "0E": 3,
    "0F": 3,
    "10": 4,  # 2 Datenbytes
    "1F": 4,
    "2F": 3,
    "42": 4,
    "14": 3,
}


class OBDReader:
    def __init__(self, config: dict):
        self.config = config
        conn = config.get("connection", {})
        self.host = conn.get("host", "192.168.0.10")
        self.port = int(conn.get("port", 35000))
        self.poll_interval = config.get("poll_interval_ms", 200) / 1000.0
        self.sock: Optional[socket.socket] = None
        # DTC-Datenbank einmalig beim Start laden (Lazy Cache)
        self._dtc_db: Optional[dict] = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.host, self.port))
        log.info(f"WiFi-Verbindung hergestellt ({self.host}:{self.port})")

        for cmd in ["ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP6"]:
            self._cmd(cmd)
            time.sleep(0.1)

        log.info("ELM327 initialisiert")

    def _read_until_prompt(self, timeout: float = 1.0) -> str:
        if not self.sock:
            return ""

        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)

        buf = b""
        try:
            while True:
                chunk = self.sock.recv(1024)
                if not chunk:
                    break
                buf += chunk
                if b">" in buf:
                    break
        except socket.timeout:
            pass
        except OSError as e:
            log.debug(f"Socket-Fehler beim Lesen: {e}")
            return ""
        finally:
            self.sock.settimeout(old_timeout)

        return buf.decode(errors="ignore")

    def _cmd(self, cmd: str) -> str:
        if not self.sock:
            return ""

        try:
            # \r ist der OBD-II Befehlsterminator für ELM327
            self.sock.sendall((cmd + "\r").encode("ascii", errors="ignore"))
            time.sleep(0.05)  # Kurze Wartezeit damit der ELM327 antworten kann
            return self._read_until_prompt(timeout=1.0)
        except (socket.timeout, OSError) as e:
            log.debug(f"CMD fehlgeschlagen ({cmd}): {e}")
            return ""

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None
            log.info("Verbindung geschlossen")

    def _parse_response(self, raw: str, pid: str) -> Optional[float]:
        clean = raw.replace(" ", "").replace("\r", "").replace("\n", "").replace(">", "").upper()
        if not clean:
            return None

        pid_upper = pid.upper()
        expected_header = f"41{pid_upper}"
        idx = clean.find(expected_header)
        if idx < 0:
            return None

        # Datenbytes beginnen NACH dem Header (Mode-Byte "41" + PID-Byte)
        header_len = len(expected_header)  # immer 4 Zeichen (z.B. "410C")
        data_start = idx + header_len

        # Anzahl der Datenbytes = Gesamtbytes - 2 (Mode + PID)
        total_bytes = EXPECTED_BYTES.get(pid_upper, 3)
        data_byte_count = total_bytes - 2  # Nur die eigentlichen Datenbytes
        hex_data = clean[data_start:data_start + data_byte_count * 2]

        try:
            d = bytes.fromhex(hex_data)
        except ValueError:
            return None

        # A und B sind die ersten beiden Datenbytes (0-basiert)
        A = d[0] if len(d) > 0 else 0
        B = d[1] if len(d) > 1 else 0

        formula = PID_FORMULAS.get(pid_upper)
        if not formula:
            return None

        try:
            return round(float(formula(A, B)), 2)
        except Exception as e:
            log.debug(f"Formel-Fehler PID {pid}: {e}")
            return None

    def read_pid(self, mode, pid):
        if not self.sock:
            return None

        try:
            mode_int = int(mode)
            pid_hex = str(pid).upper().replace("0X", "")
        except Exception:
            return None

        raw = self._cmd(f"{mode_int:02X}{pid_hex}")
        if not raw:
            return None

        val = self._parse_response(raw, pid_hex)
        if val is not None:
            log.debug(f"PID {pid_hex}: {val}")
        return val

    def read_all_pids(self):
        data = {}

        for p in self.config.get("pids", []):
            try:
                v = self.read_pid(p["mode"], p["pid"])
                if v is not None:
                    data[p["name"]] = v
            except Exception as e:
                log.debug(f"PID-Lese-Fehler {p}: {e}")

        return data

    def _get_dtc_db(self) -> dict:
        """Lädt die DTC-Datenbank einmalig und cached sie im Speicher."""
        if self._dtc_db is None:
            self._dtc_db = self._load_dtcs_database()
        return self._dtc_db

    def _load_dtcs_database(self) -> dict:
        """Liest die DTC-Datenbank aus der JSON-Datei."""
        db_path = Path(__file__).resolve().parent.parent / "data" / "dtc_database.json"
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"DTC-Datenbank konnte nicht geladen werden ({db_path}): {e}")
            return {}

    def read_dtcs(self) -> List[Dict[str, Any]]:
        """
        Liest Fehlercodes (DTCs) aus dem Steuergerät.

        Verwendet OBD-II Mode 03 (kein PID), um die aktiven DTCs abzurufen.
        Die ECU antwortet mit '43 XX XX ...' wobei je 2 Bytes einen DTC ergeben.

        Gibt eine Liste von Dicts zurück mit: code, description, category,
        severity, typical_causes, status.
        """
        if not self.sock:
            log.warning("OBD-Socket nicht verbunden")
            return []

        # Mode 03: Stored DTCs lesen – kein PID, nur der Mode-Byte
        raw = self._cmd("03")
        if not raw:
            log.debug("Keine Antwort vom Steuergerät auf DTC-Anfrage")
            return []

        # Erwartetes Antwortformat: "43 XX XX XX XX ..."
        # "43" ist die positive Response auf Mode 03
        clean = raw.replace(" ", "").replace("\r", "").replace("\n", "").replace(">", "").upper()

        if not clean.startswith("43"):
            log.debug(f"Unerwartete Antwort auf Mode-03-Anfrage: {raw!r}")
            return []

        # Header "43" entfernen, Rest sind DTC-Bytes (je 2 Bytes = 4 Hex-Zeichen pro DTC)
        hex_data = clean[2:]

        dtc_codes = []
        for i in range(0, len(hex_data), 4):
            byte_pair = hex_data[i:i + 4]
            if len(byte_pair) < 4:
                break

            # "00 00" bedeutet kein weiterer DTC (Padding)
            if byte_pair == "0000":
                continue

            try:
                b1 = int(byte_pair[0:2], 16)
                b2 = int(byte_pair[2:4], 16)

                # Bits 7-6 von b1 bestimmen das erste Zeichen:
                # 00 = P (Powertrain), 01 = C (Chassis),
                # 10 = B (Body),       11 = U (Network)
                char1 = ["P", "C", "B", "U"][b1 >> 6]

                # Bits 5-4 von b1: zweites Zeichen (0-3)
                char2 = f"{(b1 & 0x3F) >> 4:X}"

                # Bits 3-0 von b1: drittes Zeichen (0-F)
                char3 = f"{b1 & 0x0F:X}"

                # b2 komplett: viertes + fünftes Zeichen
                char4 = f"{(b2 >> 4) & 0x0F:X}"
                char5 = f"{b2 & 0x0F:X}"

                dtc = f"{char1}{char2}{char3}{char4}{char5}"
                dtc_codes.append(dtc)

            except (ValueError, IndexError) as e:
                log.debug(f"Fehler beim Parsen des DTC-Byte-Paars {byte_pair!r}: {e}")
                continue

        if not dtc_codes:
            log.debug("Keine aktiven DTCs gefunden")
            return []

        dtc_db = self._get_dtc_db()
        results = []
        for code in dtc_codes:
            info = dtc_db.get(code, {
                "description": "Unbekannter Fehlercode",
                "category": "Unknown",
                "severity": "info",
                "typical_causes": ["Keine Informationen verfügbar"]
            })
            results.append({
                "code": code,
                "description": info.get("description", "Unbekannter Fehlercode"),
                "category": info.get("category", "Unknown"),
                "severity": info.get("severity", "info"),
                "typical_causes": info.get("typical_causes", []),
                "status": "CONFIRMED",
            })

        log.info(f"{len(results)} DTC(s) gefunden: {[r['code'] for r in results]}")
        return results

    def clear_dtcs(self) -> bool:
        """
        Löscht alle gespeicherten Fehlercodes (DTCs).

        Verwendet OBD-II Mode 04 (kein PID). Bei Erfolg antwortet
        das Steuergerät mit '44' (positive Response auf Mode 04).

        Gibt True bei Erfolg zurück, sonst False.
        """
        if not self.sock:
            log.warning("OBD-Socket nicht verbunden")
            return False

        # Mode 04: DTCs löschen – kein PID, nur der Mode-Byte
        raw = self._cmd("04")
        if not raw:
            log.debug("Keine Antwort vom Steuergerät auf DTC-Lösch-Befehl")
            return False

        # Positive Response auf Mode 04 ist "44" (kein weiterer Payload)
        clean = raw.replace(" ", "").replace("\r", "").replace("\n", "").replace(">", "").upper()

        if "44" not in clean:
            log.debug(f"Unerwartete Antwort auf Mode-04-Befehl: {raw!r}")
            return False

        # Kurze Wartezeit damit das Steuergerät die DTCs vollständig löscht
        time.sleep(0.5)
        log.info("DTCs erfolgreich gelöscht")
        return True