"""
TinyLLM Interface – Chat mit den Fahrzeugdaten
Nutzt llama.cpp mit einem quantisierten TinyLLM/Phi-3 Modell
"""

import logging
import json
from pathlib import Path

log = logging.getLogger("llm")

SYSTEM_PROMPT = """Du bist CarGPT, der smarte Assistent für dein Fahrzeug.
Du hilfst bei Fragen zu Motordaten, Fahrzeugzustand und Anomalie-Erkennung.
Antworte kurz und präzise. Nutze Emojis sparsam.
Wenn du Fahrzeugdaten analysierst, beziehe dich immer auf die übergebenen aktuellen Werte."""

class LLMInterface:
    def __init__(self, model_path: str = None, config_path: str = None):
        self.model_path = model_path
        self.llm = None
        self.ready = False

        if model_path and Path(model_path).exists():
            self._init_llm()
        else:
            log.warning("TinyLLM Modell nicht gefunden – Chat deaktiviert")

    def _init_llm(self):
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False
            )
            self.ready = True
            log.info(f"TinyLLM geladen: {self.model_path}")
        except Exception as e:
            log.error(f"TinyLLM Init fehlgeschlagen: {e}")

    def build_context(self, current_data: dict, anomaly_score: float = 0.0,
                     recent_alerts: list = None) -> str:
        """Baut den Prompt-Kontext aus aktuellen Fahrzeugdaten"""
        data_str = "\n".join([f"- {k}: {v}" for k, v in current_data.items() if v is not None])
        alerts_str = "\n".join([f"- {a}" for a in (recent_alerts or [])])

        return (
            f"Aktuelle Motordaten:\n{data_str}\n\n"
            f"Anomalie-Score: {anomaly_score:.4f}\n"
            f"Letzte Alarme: {alerts_str or 'Keine'}\n"
        )

    def ask(self, question: str, current_data: dict,
            anomaly_score: float = 0.0, recent_alerts: list = None) -> str:
        """Stellt eine Frage an das LLM mit aktuellen Fahrzeugdaten"""
        if not self.ready:
            return "LLM nicht verfügbar – lade zuerst ein Modell."

        context = self.build_context(current_data, anomaly_score, recent_alerts)
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{context}\n\n"
            f"Frage: {question}\n"
            f"Antwort:"
        )

        try:
            output = self.llm(
                full_prompt,
                max_tokens=256,
                temperature=0.3,
                stop=["Frage:", "\n\n"]
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            log.error(f"LLM Fehler: {e}")
            return f"LLM Fehler: {e}"