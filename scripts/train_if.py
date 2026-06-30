#!/usr/bin/env python3
"""
Trainiert das Isolation Forest Modell auf Baseline-Daten
"""

import argparse
import logging

log = logging.getLogger("train")


def train(input_csv: str = "data/training/baseline.csv",
          output_model: str = "models/isolation_forest.joblib",
          contamination: float = 0.05):
    from src.analytics.anomaly_detector import AnomalyTrainer
    AnomalyTrainer.train_from_csv(input_csv, output_model, contamination)
    log.info(f"Training abgeschlossen. Modell: {output_model}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Trainiert das Isolation-Forest-Modell auf Baseline-Daten."
    )
    parser.add_argument(
        "--input",
        default="data/training/baseline.csv",
        help="Pfad zur Baseline-CSV."
    )
    parser.add_argument(
        "--output",
        default="models/isolation_forest.joblib",
        help="Zielpfad für das trainierte Modell."
    )
    parser.add_argument(
        "--contamination",
        type=float,
        default=0.05,
        help="Erwarteter Anteil an Anomalien (0.0 bis 1.0)."
    )
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args()
    train(args.input, args.output, args.contamination)


if __name__ == "__main__":
    main()