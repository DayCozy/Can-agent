# CAN-Agent – KI-gestütztes Fahrzeug-Monitoring

## Überblick

Ein Edge-KI-Agent auf Raspberry Pi (+ PiCAN2), der an das Motorsteuergerät deines Mercedes C-Klasse angeschlossen ist. Er liest CAN-Bus-Daten in Echtzeit aus, erkennt Anomalien via Isolation Forest, prüft Hardlimits, und kommuniziert über Telegram.

## Architektur

```
[Motorsteuergerät] ←→ CAN-Bus ←→ [PiCAN2] → [Raspberry Pi]
                                              ├── python-can         (CAN-Interface)
                                              ├── sklearn IF         (Anomalieerkennung)
                                              ├── Hardlimit-Check    (Sofort-Alarm)
                                              ├── llama.cpp/TinyLLM   (Chat-Interface)
                                              ├── Telegram Bot        (Alerts)
                                              └── SQLite/CSV          (Data Logger)
```

## Projektstruktur

```
can-agent/
├── src/
│   ├── can_interface/      # python-can, OBD2-PID-Requests
│   ├── analytics/          # Isolation Forest, Hardlimit-Engine
│   ├── alerts/             # Telegram-Bot Integration
│   ├── llm_interface/      # TinyLLM Chat-Interface
│   └── data_logger/        # SQLite + CSV Export
├── config/
│   ├── hardlimits.json     # Fahrzeugspezifische Schwellwerte
│   ├── obd_pids.json       # Abgefragte OBD2-PIDs
│   └── telegram.json       # Bot-Token, Chat-ID
├── models/                 # Trainierte Isolation-Forest-Modelle
├── data/
│   ├── logs/               # Rohdaten-Logs
│   └── training/           # Trainingsdaten für IF
├── scripts/
│   ├── setup_pi.sh         # Pi + PiCAN2 Erst-Setup
│   ├── collect_baseline.py # Daten sammeln für Training
│   └── train_if.py         # Isolation Forest trainieren
└── docs/                   # Hardware-Links, MB-CAN-Notes
```

## Status

- [ ] Phase 1: Pi + PiCAN2 zum Laufen bringen
- [ ] Phase 2: OBD2-PIDs auslesen & Daten loggen
- [ ] Phase 3: Baseline-Daten sammeln (10-20 Fahrten)
- [ ] Phase 4: Isolation Forest trainieren
- [ ] Phase 5: Hardlimits implementieren
- [ ] Phase 6: Telegram-Alerts
- [ ] Phase 7: TinyLLM integrieren

## Hardware

- Raspberry Pi 4 oder 5 (4GB+)
- PiCAN2 SMPS (Dual) für Raspberry Pi 3/4
- OBD2 zu DB9 Kabel (OBD2 Stecker am Auto)
- 12V Stromversorgung über KfZ-Board

## Quick Setup (Pi)

```bash
# PiCAN2 Treiber & can-utils
sudo apt update && sudo apt install can-utils

# Python Dependencies
pip install python-can python-obd scikit-learn pandas sqlite3 llama-cpp-python

# CAN Interface aktivieren
sudo ip link set can0 up type can bitrate 500000
```

## Links

- [python-can Docs](https://python-can.readthedocs.io/)
- [PiCAN2 Documentation](https://www.raspberrypi.org/forums/viewtopic.php?t=141052)
- [OBD2 PIDs](https://en.wikipedia.org/wiki/OBD-II_PIDs)