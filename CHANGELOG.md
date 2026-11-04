# Änderungsprotokoll

*[🇬🇧 English version](CHANGELOG.en.md)*

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Versionen folgen dem Feld `version` in `custom_components/kostal/manifest.json`.

## 2.2.0 – 2026-11-04

**Neu**
- **Eigener Client** (`client.py`) statt der Bibliothek `kostalpiko`: asynchron über die HTTP-Verbindung von Home Assistant, ohne private Methoden und ohne Versionsbegrenzung. Das Auslesen der Seiten beruht auf `kostalpiko` (MIT, siehe [NOTICE](NOTICE)). Getestet mit Beispielseiten von fünf Layouts und den Seiten eines echten PIKO 10.1.
- **Falsches Passwort wird erkannt** (HTTP 401): Beim Einrichten erscheint „Benutzername oder Passwort ist falsch“, im Betrieb startet Home Assistant eine **erneute Anmeldung** (Reauth) statt endlos Fehler zu loggen.
- **Skript `scripts/check_inverter.py`** liest einen Wechselrichter mit dem Client aus und gibt alle Werte aus (Passwort wird abgefragt).

**Geändert**
- **Wirkungsgrad geglättet:** Er wird über die letzten 5 Minuten gemittelt (Summe AC ÷ Summe DC) statt aus einem einzelnen Abruf berechnet, der bei wechselnder Einstrahlung um mehrere Prozent schwankte.
- Abhängigkeit `lxml` statt `kostalpiko`. Mindestversion Home Assistant **2025.8.0** (Options-Flow lädt die Integration selbst neu).
- Eine unbekannte Seitenstruktur (andere Anzahl von Werten) wird als Fehler gemeldet statt still „unbekannt“ zu liefern.
- Die BA-Sensoren zeigen die vom Wechselrichter gelieferten Werte (z. B. 0 W) statt eines Textes „No BA sensor installed“.

## 2.1.0 – 2026-11-04

**Neu**
- **Berechnete Sensoren:** *String 1/2/3 power* (Spannung × Strom je String), *DC power* (Summe) und *Efficiency* (AC ÷ DC in %). Sie ersetzen entsprechende Template-Sensoren. Ohne DC-Eingang (Standby) ist der Wirkungsgrad „unbekannt“ statt 0 %.
- **Neu konfigurieren:** Host und Zugangsdaten lassen sich ändern, ohne die Integration zu löschen (Ablehnung bei anderer Seriennummer). Entitäten und Verlauf bleiben erhalten.
- **Diagnose-Download** (Host, Benutzername, Passwort und Seriennummer geschwärzt) und `PARALLEL_UPDATES`.
- **Options-Flow:** Die überwachten Sensoren lassen sich nachträglich über **Konfigurieren** ändern, ohne die Integration zu löschen. Entity-IDs bleiben erhalten.
- **Übersetzungen:** Deutsch und Englisch für Einrichtung, Optionen und Fehlermeldungen.
- **Tests:** Automatisierte Tests gegen Home Assistant 2026.10.4 (Config-Flow, Options-Flow, Einrichtung, Entladen/Neuladen, Erhalt bestehender Entitäten, Berechnungen).

**Geändert**
- **Ausfall wird erkannt:** Nach drei fehlgeschlagenen Abrufen in Folge (~1,5 Minuten) werden die Sensoren „nicht verfügbar“ statt veraltete Werte weiterzuzeigen; Ausfall und Wiederherstellung werden je einmal geloggt. Die Bibliothek `kostalpiko` verschluckt Netzwerkfehler, deshalb werden die Seiten des Wechselrichters jetzt direkt abgefragt (`kostalpiko` auf `>=0.6,<0.7` begrenzt). Ohne diese Änderung zeigten Sensoren bei einem Ausfall weiter den letzten Wert.
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
