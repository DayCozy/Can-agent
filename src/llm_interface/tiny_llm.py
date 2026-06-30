#!/usr/bin/env python3
"""
TinyLLM Interface – Chat mit den Fahrzeugdaten
Nutzt Ollama (REST API) mit phi3:3.8b Modell
"""

import logging
import time
import requests

log = logging.getLogger("llm")

SYSTEM_PROMPT = (
    "Du bist CarGPT, der smarte Assistent für ein Fahrzeug.\n"
    "Du hilfst bei Fragen zu Motordaten, Fahrzeugzustand und Anomalie-Erkennung.\n"
    "Antworte kurz, präzise und beziehe dich nur auf die übergebenen aktuellen Werte."
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:3.8b"
MIN_REQUEST_INTERVAL = 5.0  # Sekunden zwischen LLM-Calls (Rate-Limit-Schutz)


class LLMInterface:
    def __init__(self, model_name: str = MODEL_NAME, ollama_url: str = OLLAMA_URL):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.ready = False
        self._last_request_time = 0.0

        self._check_ollama()

    def _check_ollama(self):
        """Prüft ob Ollama erreichbar ist"""
        try:
            response = requests.get(
                "http://localhost:11434/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]
                if self.model_name in model_names:
                    self.ready = True
                    log.info(f"Ollama bereit mit Modell: {self.model_name}")
                else:
                    log.warning(
                        f"Modell {self.model_name} nicht in Ollama gefunden. "
                        f"Verfügbare Modelle: {model_names}"
                    )
            else:
                log.warning(f"Ollama antwortet mit Status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            log.warning("Ollama nicht erreichbar – Chat deaktiviert")
        except requests.exceptions.Timeout:
            log.warning("Ollama Timeout – Chat deaktiviert")
        except Exception as e:
            log.warning(f"Ollama-Check fehlgeschlagen: {e}")

    def _rate_limit(self):
        """Stellt sicher, dass zwischen Requests genug Zeit vergeht"""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            log.debug(f"Rate-Limit: Warte {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def build_context(self, current_data: dict, anomaly_score: float = 0.0,
                     recent_alerts: list = None) -> str:
        """Baut den Prompt-Kontext aus aktuellen Fahrzeugdaten"""
        data_str = "\n".join(
            f"- {k}: {v}" for k, v in current_data.items() if v is not None
        )
        alerts_str = "\n".join(f"- {a}" for a in (recent_alerts or [])) or "Keine"

        return (
            f"Aktuelle Motordaten:\n{data_str}\n\n"
            f"Anomalie-Score: {anomaly_score:.4f}\n"
            f"Letzte Alarme:\n{alerts_str}"
        )

    def ask(self, question: str, current_data: dict,
            anomaly_score: float = 0.0, recent_alerts: list = None) -> str:
        """
        Stellt eine Frage an das LLM mit aktuellen Fahrzeugdaten.
        Nutzt Rate-Limiting um Ollama nicht zu überlasten.
        """
        if not self.ready:
            return (
                "LLM nicht verfügbar – Ollama läuft nicht oder Modell fehlt. "
                "Starte Ollama mit: ollama serve"
            )

        # Rate-Limit prüfen
        self._rate_limit()

        context = self.build_context(current_data, anomaly_score, recent_alerts)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{context}\n\n"
            f"Frage: {question}\n"
            f"Antwort:"
        )

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 256,
                    }
                },
                timeout=60  # phi3 braucht manchmal ~20s
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "").strip()

            if not text:
                return "Keine Antwort vom Modell erhalten."
            return text

        except requests.exceptions.ConnectionError:
            log.error("Ollama Verbindung verloren")
            self.ready = False
            return "LLM Verbindung verloren – bitte Ollama neu starten."
        except requests.exceptions.Timeout:
            log.error("Ollama Timeout bei Anfrage")
            return "LLM Timeout – Modell braucht zu lange. Bitte erneut versuchen."
        except requests.exceptions.HTTPError as e:
            log.error(f"Ollama HTTP-Fehler: {e}")
            return f"LLM Fehler: {e}"
        except Exception as e:
            log.error(f"LLM Fehler: {e}")
            return f"LLM Fehler: {e}"