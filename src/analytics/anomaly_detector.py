"""
Anomalie-Detektor mit Isolation Forest
Trainiert auf Baseline-Fahrtdaten, erkennt Abweichungen in Echtzeit
"""

import logging
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

log = logging.getLogger("anomaly")

FEATURE_ORDER = [
    "rpm", "coolant_temp", "oil_temp", "vehicle_speed", "throttle_position",
    "engine_load", "maf_rate", "lambda_voltage", "intake_air_temp", "fuel_pressure"
]

class AnomalyDetector:
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model = None
        self._load_model()

    def _load_model(self):
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)
            log.info(f"Modell geladen: {self.model_path}")
        else:
            log.warning("Kein Modell gefunden – Anomalieerkennung deaktiviert")

    def is_trained(self) -> bool:
        return self.model is not None

    def predict(self, data: dict) -> float:
        """Gibt Anomalie-Score zurück (0 = normal, >0 = ungewöhnlich)"""
        if not self.is_trained():
            return 0.0

        # Features in richtige Reihenfolge bringen
        features = [data.get(f, 0.0) for f in FEATURE_ORDER]
        X = np.array(features).reshape(1, -1)

        # Score: negativ = Anomalie, 0 = normal
        score = self.model.score_samples(X)[0]
        # Umwandeln zu positiver Score (je höher = desto ungewöhnlicher)
        return -score

    def predict_label(self, data: dict) -> str:
        """Gibt Label zurück: 'normal' oder 'anomalie'"""
        if not self.is_trained():
            return "unavailable"
        return "anomalie" if self.predict(data) > 0.5 else "normal"


class AnomalyTrainer:
    """Trainiert ein Isolation Forest Modell auf Baseline-Daten"""

    @staticmethod
    def train_from_csv(csv_path: str, output_path: str, contamination: float = 0.05):
        import pandas as pd
        from sklearn.model_selection import train_test_split

        df = pd.read_csv(csv_path)
        df = df.dropna(subset=FEATURE_ORDER)

        X = df[FEATURE_ORDER].values

        log.info(f"Training mit {len(X)} Samples, {len(FEATURE_ORDER)} Features")

        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output_path)
        log.info(f"Modell gespeichert: {output_path}")