import logging
import time
from enum import Enum

log = logging.getLogger("engine_state")

class EngineState(Enum):
    OFF = "off"
    STARTING = "starting"
    ON = "on"

class EngineStateMachine:
    RPM_STARTING_MIN = 50
    COOLANT_WARM_THRESHOLD = 80
    OFF_CONFIRM_SECONDS = 30

    def __init__(self):
        self.state = EngineState.OFF
        self.rpm_off_since: float | None = None
        log.info("Engine-State-Machine initialisiert (OFF)")

    def update(self, data: dict) -> EngineState:
        rpm = data.get("rpm")
        coolant = data.get("coolant_temp")

        if rpm is None:
            return self.state

        try:
            rpm = float(rpm)
        except (TypeError, ValueError):
            return self.state

        if coolant is not None:
            try:
                coolant = float(coolant)
            except (TypeError, ValueError):
                coolant = None

        now = time.time()

        if self.state == EngineState.OFF:
            if rpm >= self.RPM_STARTING_MIN:
                self.state = EngineState.STARTING
                self.rpm_off_since = None
                log.info("🔑 Motor STARTEND (RPM %.0f)", rpm)

        elif self.state == EngineState.STARTING:
            if coolant is not None and coolant >= self.COOLANT_WARM_THRESHOLD:
                self.state = EngineState.ON
                log.info("✅ Motor AN (Kühlmittel %.0f°C)", coolant)
            elif rpm < self.RPM_STARTING_MIN:
                if self.rpm_off_since is None:
                    self.rpm_off_since = now
                elif now - self.rpm_off_since > self.OFF_CONFIRM_SECONDS:
                    self.state = EngineState.OFF
                    self.rpm_off_since = None
                    log.info("🔴 Motor AUS (Kurzstarter)")

        elif self.state == EngineState.ON:
            if rpm < self.RPM_STARTING_MIN:
                if self.rpm_off_since is None:
                    self.rpm_off_since = now
                elif now - self.rpm_off_since > self.OFF_CONFIRM_SECONDS:
                    self.state = EngineState.OFF
                    self.rpm_off_since = None
                    log.info("🔴 Motor AUS (nach 30s Stillstand)")
            else:
                self.rpm_off_since = None

        return self.state

    @property
    def is_on(self) -> bool:
        return self.state == EngineState.ON

    @property
    def is_off(self) -> bool:
        return self.state == EngineState.OFF