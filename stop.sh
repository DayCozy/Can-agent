#!/bin/bash
# Car-Agent Stop-Skript – beendet alle Prozesse sauber

echo "🛑 Stoppe Car-Agent..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Lese gespeicherte PIDs
if [ -f .running_pids ]; then
    source .running_pids
    
    echo "Beende Agent (PID $AGENT_PID)..."
    kill $AGENT_PID 2>/dev/null
    
    echo "Beende Telegram-Bot (PID $BOT_PID)..."
    kill $BOT_PID 2>/dev/null
    
    # Ollama nur killen wenn wir es gestartet haben
    if [ "$OLLAMA_STARTED" = "1" ]; then
        echo "Beende Ollama (PID $OLLAMA_PID)..."
        kill $OLLAMA_PID 2>/dev/null
        sleep 1
        # Falls nicht beendet, force-kill
        kill -9 $OLLAMA_PID 2>/dev/null
    else
        echo "Ollama läuft weiter (war schon aktiv)"
    fi
    
    rm -f .running_pids
else
    # Fallback: alle Prozesse killen
    echo "Keine PIDs gefunden – beende alle Car-Agent Prozesse..."
    pkill -f can_agent.py 2>/dev/null
    pkill -f telegram_bot.py 2>/dev/null
fi

echo ""
echo "✅ Alles gestoppt!"
echo ""
echo "Falls Prozesse hängen:"
echo "  pkill -9 -f can_agent"
echo "  pkill -9 -f telegram_bot"
echo "  pkill -9 -f ollama"