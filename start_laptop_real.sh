#!/bin/bash
# Car-Agent Laptop-Modus mit realistischen OBD2-Simulationsdaten
# Nutzt OBDSim + vcan0 für echte OBD2-PID Responses ohne echte Hardware

echo "🚗 Car-Agent Laptop-Modus (Realistische OBD2-Simulation)"
echo "========================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Virtual Environment aktivieren
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "FEHLER: .venv nicht gefunden in $SCRIPT_DIR"
    exit 1
fi

# Prüfe ob Ollama läuft
echo "1. Prüfe Ollama..."
curl -s http://localhost:11434/api/tags > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "   ⚠️  Ollama nicht erreichbar!"
    echo "   Starte zuerst in einem separaten Terminal:"
    echo "   ollama serve"
    echo ""
fi

# Prüfe/Setup vcan0
echo "2. Prüfe vcan0..."
if ip link show vcan0 > /dev/null 2>&1; then
    echo "   ✅ vcan0 existiert"
else
    echo "   ⚠️  vcan0 nicht vorhanden – erstelle es..."
    sudo ip link add vcan0 type vcan
    sudo ip link set vcan0 up
    echo "   ✅ vcan0 erstellt und aktiviert"
fi

# Prüfe ob OBDSim läuft, starte wenn nicht
echo "3. Prüfe OBDSim..."
if pgrep -f "obdsim" > /dev/null; then
    echo "   ✅ OBDSim läuft bereits"
else
    echo "   ℹ️  OBDSim nicht gefunden. Starte mit:"
    echo "   obdsim -g generic -w vcan0"
    echo ""
    echo "   Oder installiere mit:"
    echo "   sudo apt install obdsim"
    echo ""
    echo "   Alternative: python-obd mit USE_MOCK_OBD=1 für Mock-Daten"
fi

# Starte CAN-Agent (KEIN Mock - nutzt python-can mit vcan0 oder echter CAN-Interface)
echo "4. Starte CAN-Agent..."
echo "   Modus: Realistische OBD2-Daten via vcan0 (OBDSim)"
echo "   (oder stelle sicher dass can0 / vcan0 verfügbar ist)"
echo ""

python can_agent.py &
AGENT_PID=$!
echo "   ✅ Agent gestartet (PID: $AGENT_PID)"

sleep 2

# Starte Telegram-Bot
echo "5. Starte Telegram-Bot..."
python telegram_bot.py &
BOT_PID=$!
echo "   ✅ Bot gestartet (PID: $BOT_PID)"

echo ""
echo "========================================================="
echo "✅ Beides läuft!"
echo ""
echo "Zum Stoppen: kill $AGENT_PID $BOT_PID"
echo ""

# Wartet auf beide Prozesse
wait