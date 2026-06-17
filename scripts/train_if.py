#!/usr/bin/env python3
"""
Trainiert das Isolation Forest Modell auf Baseline-Daten
"""
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("train")

def train(input_csv: str = "data/training/baseline.csv",
          output_model: str = "models/isolation_forest.joblib",
          contamination: float = 0.05):
    from src.analytics.anomaly_detector import AnomalyTrainer
    AnomalyTrainer.train_from_csv(input_csv, output_model, contamination)
    log.info(f"Training abgeschlossen. Modell: {output_model}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/training/baseline.csv")
    parser.add_argument("--output", default="models/isolation_forest.joblib")
    parser.add_argument("--contamination", type=float, default=0.05)
    args = parser.parse_args()
    train(args.input, args.output, args.contamination)