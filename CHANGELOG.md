# Änderungsprotokoll

*[🇬🇧 English version](CHANGELOG.en.md)*

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Versionen folgen dem Feld `version` in `custom_components/kostal/manifest.json`.

## 2.1.0 – 2026-11-04

**Neu**
- **Berechnete Sensoren:** *String 1/2/3 power* (Spannung × Strom je String), *DC power* (Summe) und *Efficiency* (AC ÷ DC in %). Sie ersetzen entsprechende Template-Sensoren. Ohne DC-Eingang (nachts) ist der Wirkungsgrad „unbekannt“ statt 0 %.
- **Options-Flow:** Die überwachten Sensoren lassen sich nachträglich über **Konfigurieren** ändern, ohne die Integration zu löschen. Entity-IDs bleiben erhalten.
- **Übersetzungen:** Deutsch und Englisch für Einrichtung, Optionen und Fehlermeldungen.
- **Tests:** Automatisierte Tests gegen Home Assistant 2026.10.4 (Config-Flow, Options-Flow, Einrichtung, Entladen/Neuladen, Erhalt bestehender Entitäten, Berechnungen).

**Geändert**
- **Gemeinsamer `DataUpdateCoordinator`** (30 s) statt eines gedrosselten Abrufs je Sensor. Die Sensoren nutzen die native Sensor-API (`native_value`, `native_unit_of_measurement`) mit echter `device_class` und `state_class` statt Attributen. Entity-ID, Name, `unique_id` und Gerät bleiben unverändert.
- **Einrichtung beim Start:** Ist der Wechselrichter nicht erreichbar, versucht Home Assistant es automatisch erneut. Bisher blieb die Integration bis zu einem manuellen Neuladen ohne Sensoren.
- **Seriennummer als Kennung** des Eintrags: derselbe Wechselrichter kann nicht doppelt angelegt werden. Bestehende Einträge erhalten sie beim nächsten Start.
- **Metadaten:** `iot_class: local_polling`, `integration_type: device`, korrekte Dokumentations- und Issue-Links; Mindestversion Home Assistant 2024.12.0.

**Korrigiert**
- **Verbindungsprüfung im Config-Flow** erkannte weder einen nicht erreichbaren Wechselrichter noch falsche Zugangsdaten und legte den Eintrag trotzdem an.
- **Hängende Updates:** Ein einzelner Netzwerkfehler konnte alle weiteren Updates bis zum Neustart blockieren.
- **Reload/Entladen:** Die Sensor-Plattform wurde nicht entladen; ein Neuladen konnte doppelte Entitäten erzeugen.
- **BA-Sensoren** lieferten den Text „No BA sensor installed“ als Zustand von Leistungssensoren; jetzt „unbekannt“.
- Fehler in der Host-Prüfung bei Einträgen ohne Host in den Daten.

**Entfernt**
- Die YAML-Einrichtung über einen `kostal:`-Block in der `configuration.yaml`. Bestehende Einträge laufen weiter.
