import json
import logging
from pathlib import Path

import telebot

log = logging.getLogger("telegram")


class TelegramAlerts:
    def __init__(self, config_path: str):
        self.bot = None
        self.chat_id = None
        self.enabled = False
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        cfg_path = Path(config_path)

        try:
            if not cfg_path.is_file():
                log.warning(f"Telegram-Config nicht gefunden: {cfg_path}")
                return

            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            token = cfg.get("bot_token")
            self.chat_id = cfg.get("chat_id")

            if token and self.chat_id:
                self.bot = telebot.TeleBot(token)
                self.enabled = True
                log.info("Telegram-Bot aktiv")
            else:
                log.warning("Telegram nicht konfiguriert (Token/Chat-ID fehlen)")
        except Exception as e:
            log.error(f"Telegram-Setup fehlgeschlagen: {e}")

    def send(self, message: str):
        if not self.enabled:
            log.info(f"[Telegram offline] {message}")
            return

        try:
            self.bot.send_message(self.chat_id, message, disable_web_page_preview=True)
        except Exception as e:
            log.error(f"Telegram send failed: {e}")

    def send_alert(self, alert: dict):
        p = alert["parameter"]
        v = alert["value"]
        lo = alert["limit_min"]
        hi = alert["limit_max"]
        u = alert["unit"]
        s = alert["severity"]

        emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(s, "⚠️")

        if v < lo:
            msg = (
                f"{emoji} {s.upper()} – {p} zu niedrig!\n"
                f"{v:.2f}{u} (Minimum: {lo}{u})"
            )
        else:
            msg = (
                f"{emoji} {s.upper()} – {p} zu hoch!\n"
                f"{v:.2f}{u} (Maximum: {hi}{u})"
            )

        self.send(msg)