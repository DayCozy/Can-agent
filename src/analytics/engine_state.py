"""
Engine State Machine
Erkennt ob der Motor AUS / STARTEND / AN ist
"""

import logging
import time
from enum import Enum

log = logging.getLogger("engine_state")


class EngineState(Enum):
    OFF = "off"
    STARTING = "starting"
    ON = "on"


class EngineStateMachine:
    """
    Logik:
      OFF     → wenn RPM < 50 für > 30 Sekunden
      STARTING → wenn RPM >= 50 aber noch nicht warm (Coolant < 80°C)
      ON      → wenn Coolant >= 80°C (warmgelaufen)

    Für Mercedes M271: Betriebstemperatur ~90-100°C,
    deshalb 80°C als Schwelle sinnvoll.
    """

    RPM_OFF_THRESHOLD = 50        # unter 50 = считается выключенным
    RPM_STARTING_MIN = 50         # ab 50 = startend
    COOLANT_WARM_THRESHOLD = 80   # ab 80°C = warm

    def __init__(self):
        self.state = EngineState.OFF
        self.rpm_off_since: float | None = None   # wann RPM zuletzt < 50 war
        self._prev_state = EngineState.OFF
        log.info("Engine-State-Machine initialisiert (OFF)")

    def update(self, data: dict) -> EngineState:
        rpm = data.get("rpm")
        coolant = data.get("coolant_temp")

        if rpm is None:
            return self.state  # keine Daten, Status halten

        rpm = float(rpm)
        coolant = coolant if coolant is not None else 0.0

        now = time.time()

        # ── OFF ──────────────────────────────────────
        if self.state == EngineState.OFF:
            if rpm >= self.RPM_STARTING_MIN:
                self.state = EngineState.STARTING
                self.rpm_off_since = None
                log.info("🔑 Motor STARTEND (RPM %.0f)", rpm)

        # ── STARTING ─────────────────────────────────
        elif self.state == EngineState.STARTING:
            if coolant >= self.COOLANT_WARM_THRESHOLD:
                self.state = EngineState.ON
                log.info("✅ Motor AN (Kühlmittel %.0f°C)", coolant)
            elif rpm < self.RPM_STARTING_MIN:
                # Zurück zu OFF wenn RPM wieder auf 0
                self.state = EngineState.OFF
                log.info("🔴 Motor AUS (Kurzstarter)")

        # ── ON ───────────────────────────────────────
        elif self.state == EngineState.ON:
            if rpm < self.RPM_STARTING_MIN:
                # Zuerst Timer starten wenn nicht schon
                if self.rpm_off_since is None:
                    self.rpm_off_since = now
                elif now - self.rpm_off_since > 30:
                    self.state = EngineState.OFF
                    self.rpm_off_since = None
                    log.info("🔴 Motor AUS (nach 30s Stillstand)")
            else:
                # RPM wieder da → Timer zurücksetzen
                self.rpm_off_since = None

        return self.state

    @property
    def is_on(self) -> bool:
        return self.state == EngineState.ON

    @property
    def is_off(self) -> bool:
        return self.state == EngineState.OFF

    def check_and_transition(self, data: dict) -> EngineState:
        """Alias für update() – einfachere Benennung."""
        return self.update(data)