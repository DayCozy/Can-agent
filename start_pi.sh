#!/bin/bash
# Car-Agent Raspberry Pi Start-Skript
# Für echten CAN-Bus Betrieb am Auto (Pi + PiCAN2)

echo "🚗 Car-Agent Pi-Modus (Echter CAN-Bus)"
echo "======================================"
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
    echo "   Starte Ollama zuerst mit: ollama serve"
    echo "   (In einem separaten Terminal oder als Service)"
    echo ""
fi

# CAN-Interface prüfen und starten
echo "2. Prüfe CAN-Interface (can0)..."
if ip link show can0 > /dev/null 2>&1; then
    echo "   ✅ can0 existiert bereits"
else
    echo "   ⚠️  can0 nicht vorhanden – versuche einzurichten..."
    echo "   Führe aus:"
    echo "   sudo ip link set can0 up type can bitrate 500000"
    echo "   Oder prüfe ob PiCAN2 Treiber geladen ist."
    echo ""
fi

# Starte CAN-Agent mit echtem OBD-Reader
echo "3. Starte CAN-Agent (Echter Modus – kein Mock)..."
python can_agent.py &
AGENT_PID=$!
echo "   ✅ Agent gestartet (PID: $AGENT_PID)"

sleep 2

# Starte Telegram-Bot
echo "4. Starte Telegram-Bot..."
python telegram_bot.py &
BOT_PID=$!
echo "   ✅ Bot gestartet (PID: $BOT_PID)"

echo ""
echo "======================================"
echo "✅ Beides läuft!"
echo ""
echo "Zum Stoppen: kill $AGENT_PID $BOT_PID"
echo ""
echo "Hinweis: CAN0 muss separat eingerichtet sein:"
echo "  sudo ip link set can0 up type can bitrate 500000"
echo ""

# Wartet auf beide Prozesse
wait