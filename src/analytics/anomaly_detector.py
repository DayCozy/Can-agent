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
        if not self.is_trained():
            return 0.0

        features = [float(data.get(f, 0.0) or 0.0) for f in FEATURE_ORDER]
        X = np.array(features, dtype=float).reshape(1, -1)
        score = self.model.decision_function(X)[0]
        return -score

    def predict_label(self, data: dict) -> str:
        if not self.is_trained():
            return "unavailable"
        return "anomalie" if self.predict(data) > 0 else "normal"


class AnomalyTrainer:
    @staticmethod
    def train_from_csv(csv_path: str, output_path: str, contamination: float = 0.05):
        import pandas as pd

        df = pd.read_csv(csv_path)

        for col in FEATURE_ORDER:
            df[col] = pd.to_numeric(df[col], errors="coerce")

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

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, out)
        log.info(f"Modell gespeichert: {out}")