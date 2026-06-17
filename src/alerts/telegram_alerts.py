"""
Telegram Bot Alert-Interface
Sendet Alarme und Status-Updates an dein Handy
"""

import json
import logging
from pathlib import Path
import telebot
from telebot import types

log = logging.getLogger("telegram")

class TelegramAlerts:
    def __init__(self, config_path: str):
        self.bot = None
        self.chat_id = None
        self.enabled = False
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            token = cfg.get("bot_token")
            self.chat_id = cfg.get("chat_id")
            if token and self.chat_id:
                self.bot = telebot.TeleBot(token, parse_mode="Markdown")
                self.enabled = True
                log.info("Telegram-Bot aktiv")
            else:
                log.warning("Telegram nicht konfiguriert (Token/Chat-ID fehlen)")
        except FileNotFoundError:
            log.warning(f"Telegram-Config nicht gefunden: {config_path}")
        except Exception as e:
            log.error(f"Telegram-Setup fehlgeschlagen: {e}")

    def send(self, message: str):
        if not self.enabled:
            log.info(f"[Telegram offline] {message}")
            return
        try:
            self.bot.send_message(self.chat_id, message)
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
            msg = f"{emoji} *{s.upper()}* – {p} zu niedrig!\n`{v:.2f}{u}` (Minimum: {lo}{u})"
        else:
            msg = f"{emoji} *{s.upper()}* – {p} zu hoch!\n`{v:.2f}{u}` (Maximum: {hi}{u})"

        self.send(msg)