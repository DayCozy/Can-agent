# DTC Diagnose-Feature für Car-Agent - Entwurf

**Status**: Entwurf abgeschlossen  
**Erstellt**: 2026-06-29  
**Autor**: Jarvis (dein AI-Assistent)

## Überblick
Dieses Feature erweitert deinen Car-Agent um die Fähigkeit, Fehlerdiagnose-Trouble-Codes (DTCs) auszulesen, zu löschen und dem Nutzer verständliche Beschreibungen zu geben – genau wie du es dir gewünscht hast!

## Kernfunktionen
✅ **DTCs auslesen** (OBD2 PID 03)  
✅ **Status anzeigen** (CONFIRMED, PENDING usw.)  
✅ **Verständliche Beschreibungen** mit Kategorie, Schweregrad und typischen Ursachen  
✅ **Fehlerspeicher löschen** (OBD2 PID 04) mit Bestätigungsabfrage  
✅ **Nachkontrolle** um persistierende Probleme zu zeigen  
✅ **Integration in car_context.json** für LLM-Zugriff  
✅ **Telegram-Bot Commands**: `/dtc` und `/clear_dtc`

## Architektur im Überblick
1. **OBD Reader Erweiterung** (`src/can_interface/obd_reader.py`): Neue Methoden `read_dtcs()` und `clear_dtcs()`
2. **Lokale DTC-Datenbank** (`data/dtc_database.json`): Lookup-Tabelle für Code→Beschreibung
3. **Car Agent Integration** (`can_agent.py`: Liest/Anreicherung/Speicherung der DTCs
4. **Telegram-Bot Erweiterung** (`telegram_bot.py`: Neue Commands für Abfrage und Löschen

## Datenfluss Beispiel
**Roh-DTCs**: `["P0171", "P0300"]`  
→ **Anreicherung**:
  - P0171 → "System too Lean (Bank 1)", Kategorie: "Fuel and Air Metering", Schweregrad: "warning"
  - P0300 → "Random/Multiple Cylinder Misfire Detected", Kategorie: "Ignition System", Schweregrad: "critical"
→ **Speicherung in car_context.json**:
```json
{
  "data": {...aktuelle Sensordaten...},
  "anomaly_score": 0.02,
  "engine_state": "ON",
  "dtcs": [
    {"code":"P0171", "description":"System too Lean (Bank 1)", ...},
    {"code":"P0300", "description":"Random/Multiple Cylinder Misfire Detected", ...}
  ]
}
```

## Sicherheit & UX
- **Bestätigung vor Löschen**: Telegram-Bot fragt "Wirklich alle DTCs löschen? (ja/nein)"
- **OBD2-Standard konform**: Löscht nur emissionsbezogene DTCs (Mode 04 PID 04)
- **Sofort-Feedback**: Nach Löschen wird neu ausgelesen, um persistierende Probleme zu zeigen
- **Klare Info bei keinen DTCs**: "Keine Fehlercodes im Speicher"

## Weiterentwicklungsmöglichkeiten (optional)
- DTC-DB über OBD-Mode 09 (VIN, CALID) für Fahrzeugspezifika erweitern
- LLM-basierte Erklärung für unbekannte/herstellerspezifische Codes
- DTC-Verlauf in `data/dtc_history.json` speichern

## Nächste Schritte
Der vollständige Entwurf mit detaillierten Implementierungsschritten befindet sich in:  
`/home/kubilay_suhta/.openclaw/workspace/can-agent/docs/dtc_feature.md`

Wenn du mit dem Entwurf zufrieden bist, können wir damit beginnen, die einzelnen Komponenten schrittweise umzusetzen – beginnend mit der DTC-Datenbank und der OBD Reader-Erweiterung.

Möchtest du das Feature so umsetzen, oder gibt es noch etwas, das du anpassen möchtest? 😊