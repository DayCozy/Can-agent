#!/usr/bin/env python3
"""
Telegram bot that uses LLMInterface to answer questions about the vehicle.
Läuft als eigenständiger Bot parallel zum CAN-Agenten.
Kommuniziert mit dem CAN-Agenten über eine IPC-Kommandodatei (commands.json).
"""

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from src.llm_interface.tiny_llm import LLMInterface
from src.context.car_context import update as update_context


log = logging.getLogger("telegram_car_bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

BASE_DIR            = Path(os.getenv("CAN_AGENT_DIR", Path(__file__).resolve().parent))
TELEGRAM_CONFIG     = BASE_DIR / "config" / "telegram.json"
CONTEXT_FILE        = BASE_DIR / "src" / "car_context.json"
COMMAND_FILE        = BASE_DIR / "data" / "commands.json"   # IPC mit CAN-Agent

SEVERITY_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴"}


# ---------------------------------------------------------------------------
# Telegram-Hilfsfunktionen
# ---------------------------------------------------------------------------

def load_config() -> dict:
    return json.loads(TELEGRAM_CONFIG.read_text(encoding="utf-8"))


def get_bot_info(token: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())["result"]


def get_updates(token: str, offset: int | None = None, timeout: int = 25) -> list:
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout={timeout}"
    if offset is not None:
        url += f"&offset={offset}"
    with urllib.request.urlopen(url, timeout=timeout + 10) as r:
        return json.loads(r.read()).get("result", [])


def send_message(token: str, chat_id: str, text: str) -> dict:
    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               "Markdown",
        "disable_web_page_preview": True,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Fahrzeug-Kontext
# ---------------------------------------------------------------------------

def read_context() -> dict | None:
    if not CONTEXT_FILE.exists():
        return None
    try:
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Konnte car_context.json nicht lesen: {e}")
        return None


def fmt(val) -> str:
    """Formatiert einen Wert auf 2 Nachkommastellen oder gibt 'N/A' zurück."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return str(val)


# ---------------------------------------------------------------------------
# IPC: Befehl an CAN-Agent senden
# ---------------------------------------------------------------------------

def send_command(action: str, params: dict | None = None) -> bool:
    """
    Schreibt einen Befehl in die IPC-Datei, die der CAN-Agent periodisch prüft.
    Gibt False zurück wenn die Datei nicht geschrieben werden konnte.
    """
    try:
        COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        command = {"action": action, "params": params or {}, "timestamp": time.time()}
        COMMAND_FILE.write_text(json.dumps(command), encoding="utf-8")
        log.info(f"IPC-Befehl gesendet: {action}")
        return True
    except Exception as e:
        log.error(f"Konnte IPC-Befehl nicht schreiben: {e}")
        return False


# ---------------------------------------------------------------------------
# Command-Handler
# ---------------------------------------------------------------------------

def handle_help(token: str, chat_id: str):
    send_message(token, chat_id,
        "🚗 *CarGPT – Verfügbare Commands:*\n"
        "/status     – Kurzer Fahrzeugüberblick\n"
        "/dtc        – Fehlercodes anzeigen\n"
        "/clear\\_dtc – Fehlercodes löschen (mit Bestätigung)\n"
        "/help       – Diese Hilfe\n\n"
        "Oder einfach eine Frage stellen!\n"
        "z.B. _\"Wie ist der Motorzustand?\"_"
    )


def handle_status(token: str, chat_id: str):
    ctx = read_context()
    if not ctx:
        send_message(token, chat_id, "⚠️ Konnte Fahrzeugdaten nicht laden.")
        return

    data    = ctx.get("data", {})
    state   = ctx.get("engine_state", "unbekannt")
    anomaly = ctx.get("anomaly_score", 0.0)

    send_message(token, chat_id,
        f"📊 *Fahrzeug-Status*\n"
        f"Motor:         {state}\n"
        f"RPM:           {fmt(data.get('rpm'))}\n"
        f"Geschwindigkeit: {fmt(data.get('vehicle_speed'))} km/h\n"
        f"Kühlmittel:    {fmt(data.get('coolant_temp'))}°C\n"
        f"Öl-Temp:       {fmt(data.get('oil_temp'))}°C\n"
        f"Batterie:      {fmt(data.get('battery_voltage'))} V\n"
        f"Kraftstoff:    {fmt(data.get('fuel_level'))}%\n"
        f"Anomalie-Score: {fmt(anomaly)}"
    )


def handle_dtc(token: str, chat_id: str):
    ctx = read_context()
    if not ctx:
        send_message(token, chat_id, "⚠️ Konnte Fahrzeugdaten nicht laden.")
        return

    dtcs = ctx.get("dtcs", [])
    if not dtcs:
        send_message(token, chat_id, "✅ Keine Fehlercodes gespeichert.")
        return

    lines = ["🔍 *Fehlerspeicher:*"]
    for dtc in dtcs:
        code   = dtc.get("code", "????")
        desc   = dtc.get("description", "Unbekannter Fehler")
        cat    = dtc.get("category", "Unbekannt")
        sev    = dtc.get("severity", "info")
        emoji  = SEVERITY_EMOJI.get(sev, "⚪")
        causes = ", ".join(dtc.get("typical_causes", ["Unbekannt"])[:2])
        lines += [
            f"{emoji} *{code}*: {desc}",
            f"   Kategorie: {cat} | Schweregrad: {sev}",
            f"   Typische Ursachen: {causes}",
            "",
        ]
    send_message(token, chat_id, "\n".join(lines))


def handle_clear_dtc_request(token: str, chat_id: str, state: dict):
    state["awaiting_confirmation"] = True
    state["action"]                = "clear_dtc"
    send_message(token, chat_id,
        "⚠️ *Wirklich alle Fehlercodes löschen?*\n"
        "Antworte mit `JA` zum Bestätigen oder mit etwas anderem zum Abbrechen."
    )


def handle_confirmation(token: str, chat_id: str, text: str, state: dict):
    if text.strip().upper() != "JA":
        state["awaiting_confirmation"] = False
        state["action"]                = None
        send_message(token, chat_id, "❌ Aktion abgebrochen.")
        return

    action = state["action"]
    state["awaiting_confirmation"] = False
    state["action"]                = None

    if action == "clear_dtc":
        # IPC: CAN-Agent führt den Clear aus – kein zweiter OBD-Socket!
        ok = send_command("clear_dtc")
        if ok:
            send_message(token, chat_id,
                "✅ Lösch-Befehl an CAN-Agent gesendet.\n"
                "Der Fehlerspeicher wird beim nächsten Zyklus geleert."
            )
        else:
            send_message(token, chat_id,
                "❌ Konnte Befehl nicht senden – IPC-Datei nicht beschreibbar."
            )


def handle_llm_question(token: str, chat_id: str, text: str, llm: LLMInterface):
    if not llm.ready:
        send_message(token, chat_id,
            "🤖 LLM gerade nicht verfügbar. Bitte später nochmal fragen."
        )
        return

    ctx     = read_context() or {}
    data    = ctx.get("data", {})
    anomaly = ctx.get("anomaly_score", 0.0)

    send_message(token, chat_id, "🤖 Denke nach...")

    try:
        answer = llm.ask(text, data, anomaly)
        send_message(token, chat_id, answer)
        log.info(f"LLM-Antwort gesendet: {answer[:80]}...")
    except Exception as e:
        log.error(f"LLM-Fehler: {e}")
        send_message(token, chat_id, "❌ Fehler beim Generieren der Antwort.")


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def main():
    config         = load_config()
    token          = config["bot_token"]
    allowed_chat   = str(config["chat_id"])

    llm      = LLMInterface()
    bot_info = get_bot_info(token)

    if not llm.ready:
        log.warning("Ollama nicht verfügbar – LLM-Fragen werden abgelehnt")

    log.info(f"Bot: @{bot_info.get('username')} (ID: {bot_info['id']})")
    log.info("Telegram Car Bot gestartet – warte auf Nachrichten...")

    # Lokaler Zustand (kein global, kein Modulscope)
    state: dict = {"awaiting_confirmation": False, "action": None}
    last_update_id: int | None = None

    while True:
        try:
            updates = get_updates(token, offset=last_update_id, timeout=25)

            for update in updates:
                last_update_id = update["update_id"] + 1

                message = update.get("message")
                if not message:
                    continue

                # Eigene Nachrichten ignorieren
                if message.get("from", {}).get("id") == bot_info["id"]:
                    continue

                text = message.get("text", "").strip()
                if not text:
                    continue

                # Nur erlaubten Chat bedienen
                if str(message["chat"]["id"]) != allowed_chat:
                    continue

                log.info(f"Nachricht: {text!r}")
                cmd = text.lower()

                # Bestätigung für laufende Aktion abwarten
                if state["awaiting_confirmation"]:
                    handle_confirmation(token, allowed_chat, text, state)
                    continue

                if cmd in ("/help", "/start"):
                    handle_help(token, allowed_chat)
                elif cmd == "/status":
                    handle_status(token, allowed_chat)
                elif cmd == "/dtc":
                    handle_dtc(token, allowed_chat)
                elif cmd == "/clear_dtc":
                    handle_clear_dtc_request(token, allowed_chat, state)
                else:
                    handle_llm_question(token, allowed_chat, text, llm)

        except Exception as e:
            log.error(f"Fehler in der Hauptschleife: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()