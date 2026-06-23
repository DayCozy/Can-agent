#!/usr/bin/env python3
"""
Telegram bot that uses the car context and an LLM to answer questions about the vehicle.
"""
import json
import os
import time
import urllib.request
import urllib.parse

# Configuration
TELEGRAM_CONFIG_PATH = "/home/kubilay_suhta/.openclaw/workspace/can-agent/config/telegram.json"
CONTEXT_FILE_PATH = "/home/kubilay_suhta/.openclaw/workspace/can-agent/car_context.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi3:3.8b"

def load_telegram_config():
    with open(TELEGRAM_CONFIG_PATH) as f:
        return json.load(f)

def get_bot_info(token):
    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        return data["result"]

def get_updates(token, offset=None):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        return data["result"]

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    data_encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=data_encoded, method="POST")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def query_ollama(prompt, model=OLLAMA_MODEL):
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    data_encoded = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API_URL, data=data_encoded, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        return result["response"].strip()

def main():
    config = load_telegram_config()
    token = config["bot_token"]
    chat_id = config["chat_id"]

    # Get bot info to ignore our own messages
    bot_info = get_bot_info(token)
    bot_id = bot_info["id"]
    print(f"Bot ID: {bot_id}")

    last_update_id = None

    print("Starting Telegram bot for car assistant...")
    while True:
        try:
            updates = get_updates(token, offset=last_update_id)
            for update in updates:
                update_id = update["update_id"]
                # Update the offset for next time
                if last_update_id is None or update_id > last_update_id:
                    last_update_id = update_id

                # Check if this is a message
                if "message" not in update:
                    continue

                message = update["message"]
                # Ignore messages from the bot itself
                if "from" in message and message["from"]["id"] == bot_id:
                    continue

                # We only care about text messages
                if "text" not in message:
                    continue

                text = message["text"]
                from_id = message["from"]["id"]
                chat_id_msg = message["chat"]["id"]

                # Only respond to messages in the configured chat (optional, but safe)
                if str(chat_id_msg) != str(chat_id):
                    continue

                print(f"Received message from {from_id}: {text}")

                # Read the car context
                try:
                    with open(CONTEXT_FILE_PATH) as f:
                        context = json.load(f)
                except Exception as e:
                    print(f"Error reading context: {e}")
                    context = {"error": "Could not read car context"}

                # Build the prompt for the LLM
                prompt = f"""Du bist ein freundlicher und sachkundiger Auto-Assistent.
                Antworte auf Deutsch und hilfreich.

                Aktuelle Fahrzeugdaten:
                {json.dumps(context, indent=2)}

                Benutzerfrage: {text}

                Deine Antwort:"""

                # Query the LLM
                try:
                    answer = query_ollama(prompt)
                except Exception as e:
                    print(f"Error querying Ollama: {e}")
                    answer = "Entschuldigung, ich konnte gerade keine Antwort vom KI-Modell erhalten."

                # Send the answer back to the same chat
                try:
                    send_message(token, chat_id, answer)
                    print(f"Sent reply: {answer[:50]}...")
                except Exception as e:
                    print(f"Error sending message: {e}")

            # Sleep a bit to avoid hammering the API
            time.sleep(1)

        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()