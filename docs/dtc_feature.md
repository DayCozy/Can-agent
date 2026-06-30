# DTC Diagnose-Feature Design

## Überblick
Erweiterung des Car-Agent-Projekts um die Fähigkeit, Fehlerdiagnose-Trouble-Codes (DTCs) aus dem Fahrzeug auszulesen, zu löschen und dem Nutzer verständliche Beschreibungen zu geben.

## Ziele
- DTCs aus dem OBD2-FehlerSpeicher auslesen (PID 03)
- Aktuellen Status jedes Codes anzeigen (CONFIRMED, PENDING, PERMANENT, usw.)
- Jeden Code mit einer verständlichen Beschreibung versehen (Kategorie, Schweregrad, typische Ursachen)
- Möglichkeit, den Fehlerspeicher zu löschen (PID 04) mit Bestätigungsabfrage
- Nach dem Löschen erneut auslesen, um persistierende Probleme zu zeigen
- Ergebnisse im `car_context.json` ablegen für LLM-Zugriff
- Telegram-Bot-Commands zum Abfragen und Löschen bereitstellen

## Architektur

### 1. OBD Reader Erweiterung (`src/can_interface/obd_reader.py`)
- Neue Methode `read_dtcs()` → sendet OBD-Mode 01 PID 03, parses Antwort zurückliegende Liste von DTCs (z.B. `P0171`, `P0300`).
- Neue Methode `clear_dtcs()` → sendet OBD-Mode 04 PID 04 (Clear DTC Information), wartet auf Bestätigung.
- Rückgabeformat: Liste von Dictionaries:
  ```python
  {
      "code": "P0171",
      "description": "System too Lean (Bank 1)",
      "category": "Fuel and Air Metering",
      "severity": "warning",
      "status": "CONFIRMED",   # from mode $01 if supported, else assume
      "timestamp": <epoch>
  }
  ```

### 2. DTC Lookup-Datenbank
- Lokale JSON/CSV Datei unter `data/dtc_database.json` mit Einträgen für:
  - Generic Powertrain (P0xxx)
  - Generic Chassis (C0xxx)
  - Generic Body (B0xxx)
  - Generic Network (U0xxx)
  - Optional: Hersteller-spezifische P1xxx/P2xxx/P3xxx (falls bekannt)
- Jeder Eintrag: `code`, `description`, `category`, `severity` (info/warning/critical), `typical_causes` (Liste).

### 3. Integration in Car Agent (`can_agent.py`)
- Im Hauptloop (oder auf Anfrage) `obd_reader.read_dtcs()` aufrufen.
- Ergebnis durch DTC-DB anreichern → angereicherte Liste.
- In `car_context.json` unter neuem Schlüssel `"dtcs": [...]` speichern.
- Beim Löschen: `obd_reader.clear_dtcs()` aufrufen, danach erneut auslesen und updaten.

### 4. Telegram-Bot Erweiterung (`telegram_bot.py`)
- Neue Commands:
  - `/dtc` → zeigt aktuelle DTCs mit Beschreibung
  - `/clear_dtc` → fragt nach Bestätigung (`"Wirklich alle DTCs löschen? (ja/nein)"`), dann ausführt und Ergebnis zeigt.
- Bei `/status` kann optional die DTC-Zahl mit ausgegeben werden.

### 5. Datenfluss Beispiel
1. Car-Agent liest Roh-DTCs: `["P0171", "P0300"]`
2. Anreicherung via DB:
   - P0171 → `{code:"P0171", description:"System too Lean (Bank 1)", category:"Fuel and Air Metering", severity:"warning", typical_causes:["MAF sensor","Vacuum leak","Fuel pump"]}`
   - P300 → `{code:"P0300", description:"Random/Multiple Cylinder Misfire Detected", category:"Ignition System or Misfire", severity:"critical", typical_causes:["Spark plugs","Ignition coils","Fuel injectors"]}`
3. Speichern in `car_context.json`:
   ```json
   {
     "data": {...},
     "anomaly_score": 0.02,
     "engine_state": "ON",
     "dtcs": [
       {"code":"P0171", "description":"System too Lean (Bank 1)", ...},
       {"code":"P0300", "description":"Random/Multiple Cylinder Misfire Detected", ...}
     ]
   }
   ```
4. Telegram-Bot liest `car_context.json` und formatiert lesbare Nachricht.

## Dateien & Pfade
- `src/can_interface/obd_reader.py` – erweitert um `read_dtcs`, `clear_dtcs`
- `data/dtc_database.json` – statische Lookup-Tabelle (kann später erweitert werden)
- `can_agent.py` – speichert aktualisierte DTCs in `car_context.json`
- `telegram_bot.py` – neue Commands `/dtc` und `/clear_dtc`

## Sicherheit & UX
- Vor dem Löschen immer Rückfrage im Telegram-Bot (`ja/nein`).
- Löschen setzt nur *emissionsbezogene* DTCs zurück (Mode 04 PID 04) – entspricht OBD2-Standard.
- Beim Löschen wird kurz gewartet (≈1s) und dann neu ausgelesen, um sofortiges Feedback zu geben.
- Falls kein DTC vorhanden ist, entsprechende Info-Meldung anzeigen.

## Weiterentwicklung (optional)
- DTC-DB über OBD-Mode 09 (Vehicle Information) ergänzen (VIN, CALID) für Fahrzeugspezifische Anpassungen.
- Freitextsuche über LLM für unbekannte oder herstellerspezifische Codes (falls nicht in DB).
- Verlauf der DTCs in `data/dtc_history.json` speichern (Zeitstempel + Zustand).

## Implementierungs-Schritte
1. [ ] DTC-DB anlegen (`data/dtc_database.json`) mit gängigen P0-Codes.
2. [ ] `obd_reader.py`: `read_dtcs()` und `clear_dtcs()` implementieren.
3. [ ] `can_agent.py`: Loop erweitern, DTCs lesen/anreichern/speichern.
4. [ ] `telegram_bot.py`: Commands `/dtc` und `/clear_dtc` hinzufügen.
5. [ ] Tests: Mock-OBD-Reader verwenden, um Antworten zu simulieren.
6. [ ] Dokumentation im README aktualisieren.