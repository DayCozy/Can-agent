#!/bin/bash
# Car-Agent Laptop Start-Skript mit automatischer ELM327 Erkennung
# STARTET UND STOPT AUCH OLLAMA automatisch

echo "🚗 Car-Agent Laptop-Modus (Auto-Erkennung ELM327)"
echo "================================================"
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

# Lese ELM Konfig aus obd_pids.json
CONFIG_FILE="config/obd_pids.json"
if [ -f "$CONFIG_FILE" ]; then
    if command -v jq >/dev/null 2>&1; then
        ELM_HOST=$(jq -r '.connection.host // "192.168.0.10"' "$CONFIG_FILE")
        ELM_PORT=$(jq -r '.connection.port // 35000' "$CONFIG_FILE")
    else
        ELM_HOST=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('connection',{}).get('host','192.168.0.10'))")
        ELM_PORT=$(python3 -c "import json; print(int(json.load(open('$CONFIG_FILE')).get('connection',{}).get('port',35000)))")
    fi
else
    ELM_HOST="192.168.0.10"
    ELM_PORT=35000
fi

echo "ELM327 Ziel: $ELM_HOST:$ELM_PORT"

# Prüfe ob ELM327 erreichbar ist (kurzer TCP-Connect)
if timeout 2 bash -c "</dev/tcp/$ELM_HOST/$ELM_PORT" 2>/dev/null; then
    echo "✅ ELM327 Adapter erreichbar – starte im ECHTEN Modus"
    USE_MOCK_OBD=""
else
    echo "⚠️  ELM327 Adapter NICHT erreichbar – starte im MOCK-Modus"
    USE_MOCK_OBD=1
fi

# ===== OLLAMA =====
echo ""
echo "1. Prüfe/Starte Ollama..."

# Prüfe ob Ollama schon läuft
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✅ Ollama bereits aktiv"
    OLLAMA_STARTED=0
else
    echo "   ℹ️  Starte Ollama..."
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    OLLAMA_STARTED=1
    
    # Warte bis Ollama bereit ist (max 15s)
    for i in $(seq 1 15); do
        sleep 1
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "   ✅ Ollama bereit (gestartet mit PID $OLLAMA_PID)"
            break
        fi
        echo "   Warte auf Ollama... ($i/15)"
    done
fi

# Starte CAN-Agent
echo ""
echo "2. Starte CAN-Agent..."
if [ -n "$USE_MOCK_OBD" ]; then
    export USE_MOCK_OBD=1
    echo "   Modus: Mock (simulierte Daten)"
else
    unset USE_MOCK_OBD
    echo "   Modus: Echt (ELM327 Adapter)"
fi
python can_agent.py &
AGENT_PID=$!
echo "   ✅ Agent gestartet (PID: $AGENT_PID)"

sleep 2

# Starte Telegram-Bot
echo "3. Starte Telegram-Bot..."
python telegram_bot.py &
BOT_PID=$!
echo "   ✅ Bot gestartet (PID: $BOT_PID)"

echo ""
echo "================================================"
echo "✅ Alles läuft!"
echo ""
echo "   Ollama: PID $OLLAMA_PID (gestartet: $OLLAMA_STARTED)"
echo "   Agent:  PID $AGENT_PID"
echo "   Bot:    PID $BOT_PID"
echo ""
echo "Zum Stoppen (alles):"
echo "  ./stop.sh"
echo ""
echo "Oder manuell:"
echo "  kill $AGENT_PID $BOT_PID $OLLAMA_PID 2>/dev/null"
echo ""

# Speichere PIDs für stop.sh
cat > .running_pids << EOF
OLLAMA_PID=$OLLAMA_PID
OLLAMA_STARTED=$OLLAMA_STARTED
AGENT_PID=$AGENT_PID
BOT_PID=$BOT_PID
EOF

# Wartet auf beide Prozesse
wait