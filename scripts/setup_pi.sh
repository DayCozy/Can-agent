#!/bin/bash
# PiCAN2 Setup-Script für Raspberry Pi
# Führt dieses Script einmalig auf dem Pi aus

set -e

echo "=== CAN-Agent Setup für Raspberry Pi ==="

# System aktualisieren
echo "[1/5] System aktualisieren..."
sudo apt update && sudo apt upgrade -y

# CAN-Tools installieren
echo "[2/5] CAN-Tools installieren..."
sudo apt install -y can-utils net-tools

# Python Dependencies
echo "[3/5] Python Packages installieren..."
pip3 install -r requirements.txt

# CAN-Interface aktivieren
echo "[4/5] CAN-Interface can0 konfigurieren..."
# PiCAN2 nutzt can0 (standard)
# Starte bei Boot mit:
# - /etc/network/interfaces.d/can0
# - oder via systemd

sudo modprobe can
sudo modprobe mcp251xfd  # oder mcp2515 je nach PiCAN2 Version

echo "CAN0 wird konfiguriert mit 500000 bit/s..."
sudo ip link set can0 up type can bitrate 500000
echo "Aktueller Status:"
ip -details link show can0

#.cangen can0 -I 7DF -L 1 -D 81:02:01:00:00:00:00:00  # Test-Frame

echo "[5/5] Setup abgeschlossen!"
echo ""
echo "=== Nächste Schritte ==="
echo "1. Daten sammeln: python3 scripts/collect_baseline.py"
echo "2. Modell trainieren: python3 scripts/train_if.py"
echo "3. Agent starten: python3 can_agent.py"
echo ""
echo "Hinweis: CAN-Interface nach Neustart wieder aktivieren:"
echo "  sudo ip link set can0 up type can bitrate 500000"