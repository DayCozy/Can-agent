import socket
import logging
import time

log = logging.getLogger("obd_reader")


class OBDReader:
    def __init__(self, config):
        self.config = config
        conn = config.get("connection", {})
        self.host = conn.get("host", "192.168.0.10")
        self.port = conn.get("port", 35000)
        self.poll_interval = config.get("poll_interval_ms", 200) / 1000.0
        self.sock = None

    def connect(self):
        self.sock = socket.socket()
        self.sock.settimeout(5)
        self.sock.connect((self.host, self.port))
        log.info(f"WiFi-Verbindung hergestellt ({self.host}:{self.port})")

        for cmd in ["ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP6"]:
            self._cmd(cmd)
            time.sleep(0.1)

        log.info("ELM327 initialisiert")

    def _cmd(self, cmd):
        try:
            self.sock.sendall((cmd + "\r").encode())
            time.sleep(0.05)

            buf = b""
            self.sock.settimeout(1.0)

            while True:
                try:
                    c = self.sock.recv(1024)
                    if not c:
                        break
                    buf += c
                    if b">" in buf:
                        break
                except socket.timeout:
                    break

            return buf.decode(errors="ignore")
        except Exception:
            return ""

    def disconnect(self):
        if self.sock:
            self.sock.close()
            log.info("Verbindung geschlossen")

    def read_pid(self, mode, pid):
        raw = self._cmd(f"{mode:02X}{pid}")

        try:
            clean = raw.replace(" ", "").replace("\r", "").replace("\n", "").replace(">", "")

            if "41" not in clean:
                return None

            idx = clean.index("41")
            end = idx + 16 if len(clean) > idx + 16 else len(clean)
            d = bytes.fromhex(clean[idx:end])

            A = d[2] if len(d) > 2 else 0
            B = d[3] if len(d) > 3 else 0

            formulas = {
                "0C": lambda A, B: ((A * 256) + B) / 4,       # rpm
                "05": lambda A, B: A - 40,                    # coolant temp
                "5C": lambda A, B: A - 40,                    # oil temp
                "0D": lambda A, B: A,                         # speed
                "11": lambda A, B: A * 100 / 255,             # throttle pos
                "04": lambda A, B: A * 100 / 255,             # engine load
                "0A": lambda A, B: A * 3,                     # fuel pressure
                "0E": lambda A, B: A / 2 - 64,                # timing advance
                "0F": lambda A, B: A - 40,                    # intake temp
                "10": lambda A, B: ((A * 256) + B) * 0.01,    # maf
                "1F": lambda A, B: (A * 256) + B,             # runtime
                "2F": lambda A, B: A * 100 / 255,             # fuel level
                "42": lambda A, B: ((A * 256) + B) / 1000,    # control module voltage
                "14": lambda A, B: A * 0.005,                 # o2 / lambda voltage
            }

            if pid.upper() in formulas:
                val = round(formulas[pid.upper()](A, B), 2)
                log.info(f"PID {pid}: {val}")
                return val

        except Exception as e:
            log.debug(f"Parse-Fehler {pid}: {e}")

        return None

    def read_all_pids(self):
        data = {}

        for p in self.config.get("pids", []):
            v = self.read_pid(p["mode"], p["pid"])
            if v is not None:
                data[p["name"]] = v

        return data
