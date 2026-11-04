<p align="center">
  <img src="https://raw.githubusercontent.com/bertel2020/HA-kostal_piko/main/brands/logo.png" alt="Kostal Piko" width="340">
</p>

<h1 align="center">Kostal Piko</h1>

<p align="center">
  Home-Assistant-Integration für Kostal-Piko-Wechselrichter – Werte aus der Weboberfläche des Wechselrichters, komplett über die Oberfläche einrichtbar.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-18BCF2.svg?logo=home-assistant&logoColor=white" alt="Home Assistant"></a>
  <a href="https://github.com/bertel2020/HA-kostal_piko/releases"><img src="https://img.shields.io/github/v/release/bertel2020/HA-kostal_piko?sort=semver&include_prereleases" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/bertel2020/HA-kostal_piko" alt="Lizenz"></a>
  <a href="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/hassfest.yaml"><img src="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/hassfest.yaml/badge.svg" alt="hassfest"></a>
  <a href="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/hacs.yaml"><img src="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/hacs.yaml/badge.svg" alt="HACS"></a>
  <a href="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/tests.yaml"><img src="https://github.com/bertel2020/HA-kostal_piko/actions/workflows/tests.yaml/badge.svg" alt="Tests"></a>
</p>

<p align="center">
  <a href="https://buymeacoffee.com/bertel2020"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee"></a>
  <a href="https://ko-fi.com/bertel2020"><img src="https://img.shields.io/badge/Ko--fi-support-FF5E5B?logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  <a href="https://paypal.me/RobertoMartins"><img src="https://img.shields.io/badge/PayPal-donate-00457C?logo=paypal&logoColor=white" alt="PayPal"></a>
</p>

<p align="center"><em><a href="README.en.md">🇬🇧 English version</a></em></p>

Eine über die Oberfläche konfigurierbare Home-Assistant-Custom-Integration für **Kostal-Piko-Wechselrichter** mit Weboberfläche. Sie liest die Werte der Weboberfläche des Wechselrichters (`/index.fhtml`) mit einem eigenen asynchronen Client aus (das Auslesen der Seiten beruht auf der Bibliothek [`kostalpiko`](https://github.com/rcasula/kostalpiko), siehe [Danksagung](#danksagung)) und stellt sie als `sensor`-Entitäten bereit. Die Integration nutzt einen Config-Flow, einen gemeinsam genutzten `DataUpdateCoordinator` und typisierte Sensoren mit `device_class` und `state_class` – damit funktionieren Langzeitstatistiken und das Energie-Dashboard.

Dieses Projekt baut auf [rcasula/kostalpiko-homeassistant](https://github.com/rcasula/kostalpiko-homeassistant) auf (siehe [Danksagung](#danksagung)). Entity-IDs und `unique_id` der bestehenden Sensoren sind unverändert, sodass sich die Integration ohne Verlust von Verlauf und Statistiken austauschen lässt (siehe [Umstieg vom Upstream-Repository](#umstieg-vom-upstream-repository)).

## Voraussetzungen

- Home Assistant **2025.8.0** oder neuer.
- Ein Kostal-Piko-Wechselrichter, dessen Weboberfläche im Netzwerk erreichbar ist (Standard-Zugang: Benutzer `pvserver`, Passwort `pvwr`).

## Installation

### Über HACS (empfohlen)

[![HACS-Repository in My Home Assistant öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bertel2020&repository=HA-kostal_piko&category=integration)
[![Kostal Piko zu My Home Assistant hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=kostal)

1. Über den ersten Button das Kostal-Piko-Repository in HACS öffnen.
2. **Kostal Piko** herunterladen und Home Assistant neu starten.
3. Über den zweiten Button die Integration hinzufügen. Alternativ in Home
   Assistant **Einstellungen → Geräte & Dienste → Integration hinzufügen →
   Kostal Piko** öffnen.

Falls der erste Button nicht funktioniert, in HACS unter **Integrationen →
Benutzerdefinierte Repositories** `https://github.com/bertel2020/HA-kostal_piko`
als Kategorie **Integration** eintragen.

### Manuell

Das Verzeichnis `custom_components/kostal` nach
`/config/custom_components/kostal` kopieren und Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → **Kostal Piko**.

1. **Name** (Standard `Kostal Piko`): wird zum Titel der Integration (`kostal_piko`) und zum Präfix aller Entity-IDs.
2. **Host**: Adresse des Wechselrichters **mit** Protokoll, z. B. `http://192.168.1.50`.
3. **Benutzername / Passwort**: Zugang zur Weboberfläche (Standard `pvserver` / `pvwr`).
4. **Sensoren**: Auswahl der Werte, für die Entitäten angelegt werden.

Beim Speichern wird die Verbindung geprüft (inklusive Zugangsdaten). Ist der Wechselrichter nicht erreichbar oder sind die Zugangsdaten falsch, erscheint ein Fehler. Derselbe Wechselrichter kann nicht doppelt angelegt werden; als Kennung dient seine Seriennummer.

Die Auswahl der Sensoren lässt sich später über den **Konfigurieren**-Button der Integration ändern. Die Integration lädt sich dann neu; vorhandene Sensoren behalten ihre Entity-IDs.

Host, Benutzername und Passwort lassen sich über ⋮ → **Neu konfigurieren** ändern, ohne die Integration zu löschen. Gehört die neue Adresse zu einem anderen Wechselrichter (andere Seriennummer), wird die Änderung abgelehnt. Entitäten und Verlauf bleiben erhalten.

Ist der Wechselrichter beim Start von Home Assistant nicht erreichbar, versucht Home Assistant die Einrichtung automatisch erneut.

## Entities

Es wird ein **Gerät** (benannt nach dem Titel, Hersteller Kostal, Modell und Seriennummer vom Wechselrichter) mit den gewählten Sensoren angelegt. Die Entity-ID entsteht aus Titel und Sensorname, bei der Standardeinstellung also `sensor.kostal_piko_<name>`.

| Sensor | Entity-ID | Einheit | Beschreibung |
|---|---|---|---|
| Current power | `sensor.kostal_piko_current_power` | W | Aktuelle AC-Leistung |
| Total energy | `sensor.kostal_piko_total_energy` | kWh | Gesamtertrag |
| Daily energy | `sensor.kostal_piko_daily_energy` | kWh | Tagesertrag |
| String 1/2/3 voltage | `sensor.kostal_piko_string_1_voltage` … | V | DC-Spannung je String |
| String 1/2/3 current | `sensor.kostal_piko_string_1_current` … | A | DC-Strom je String |
| L1/L2/L3 voltage | `sensor.kostal_piko_l1_voltage` … | V | Netzspannung je Phase |
| L1/L2/L3 power | `sensor.kostal_piko_l1_power` … | W | Leistung je Phase |
| Status | `sensor.kostal_piko_status` | – | Betriebszustand als Text (z. B. „Einspeisen (MPP)“) |
| Solar generator power | `sensor.kostal_piko_solar_generator_power` | W | Leistung des Solargenerators (nur mit BA-Sensor) |
| Consumption phase 1/2/3 | `sensor.kostal_piko_consumption_phase_1` … | W | Verbrauch je Phase (nur mit BA-Sensor) |
| String 1/2/3 power | `sensor.kostal_piko_string_1_power` … | W | **Berechnet:** Spannung × Strom je String |
| DC power | `sensor.kostal_piko_dc_power` | W | **Berechnet:** Summe der String-Leistungen |
| Efficiency | `sensor.kostal_piko_efficiency` | % | **Berechnet:** AC-Leistung ÷ DC-Leistung |

Die Namen der Sensoren sind englisch, unabhängig von der Oberflächensprache. Die Entity-ID wird von Home Assistant einmalig bei der Erstanlage vergeben und danach beibehalten.

### Berechnete Sensoren

Die drei berechneten Werte stammen nicht direkt vom Wechselrichter, sondern werden aus den String-Werten gebildet. Sie ersetzen Template-Sensoren, die dieselbe Rechnung in der `configuration.yaml` oder als Helfer erledigen.

- **String N power** = Spannung × Strom, auf ganze Watt gerundet. Hat der Wechselrichter weniger als drei Strings, ist der Wert „unbekannt“.
- **DC power** = Summe der vorhandenen String-Leistungen.
- **Efficiency** = AC-Leistung ÷ DC-Leistung × 100, auf eine Nachkommastelle gerundet. Ohne DC-Eingang (Standby) ist der Wert „unbekannt“ und nicht 0 %, damit Durchschnittswerte nicht verfälscht werden.

### Diagnose

Unter Einstellungen → Geräte & Dienste → Kostal Piko → ⋮ → **Diagnose herunterladen** gibt es eine JSON-Datei mit dem Zustand der Integration und den aktuellen Sensorwerten. Host, Benutzername, Passwort und Seriennummer sind darin geschwärzt. Sie eignet sich gut für Fehlermeldungen.

### Verhalten bei Ausfall

Alle Sensoren werden von einem gemeinsamen Coordinator alle 30 Sekunden aktualisiert (ein Abruf pro Intervall, nicht je Sensor). Antwortet der Wechselrichter einmal oder zweimal nicht, behalten die Sensoren ihren letzten Wert. Schlagen **drei Abrufe in Folge** fehl (etwa 1,5 Minuten), werden alle Sensoren **„nicht verfügbar“** und im Log erscheint einmal eine Fehlermeldung. Sobald der Wechselrichter wieder antwortet, werden die Sensoren wieder verfügbar und die Wiederherstellung wird einmal geloggt. So zeigt kein Sensor veraltete Werte als aktuell an. Ein Ausfall des optionalen BA-Sensors macht die übrigen Werte nicht nicht verfügbar.

Im Standby (nachts) ist der Wechselrichter erreichbar und meldet den Status „Aus“; die Sensoren bleiben dann verfügbar.

### BA-Sensor

Die Sensoren *Solar generator power* und *Consumption phase 1/2/3* setzen einen Kostal-BA-Sensor (Hausverbrauchsmessung) voraus. Liefert die BA-Seite des Wechselrichters nur Nullwerte, zeigen die Sensoren 0 W; liefert sie keine Werte, sind sie „unbekannt“.

## Umstieg vom Upstream-Repository

Bei Verwendung des Repositories `rcasula/kostalpiko-homeassistant` in HACS:

1. **Backup** in Home Assistant anlegen.
2. In HACS das Repository auf `bertel2020/HA-kostal_piko` umstellen (altes Repository entfernen, neues als benutzerdefiniertes Repository hinzufügen und **Kostal Piko** herunterladen) und Home Assistant neu starten.
3. Prüfen, dass die vorhandenen `sensor.kostal_piko_*` weiter Werte liefern. Es sollten **keine** Entitäten mit der Endung `_2` entstehen: Namen, `unique_id` und Gerät sind unverändert.

## Entfernen

Einstellungen → Geräte & Dienste → **Kostal Piko** → ⋮ → **Löschen**. Dabei werden die Entitäten und das Gerät aus Home Assistant entfernt; der Verlauf bleibt gemäß den Recorder-Einstellungen erhalten. Danach kann die Integration in HACS über ⋮ → **Entfernen** deinstalliert werden. Sind keine Einträge mehr vorhanden, lässt sich das Verzeichnis `custom_components/kostal` (bei manueller Installation) löschen.

## YAML-Einrichtung entfällt

Die frühere Einrichtung über einen `kostal:`-Block in der `configuration.yaml` wird nicht mehr unterstützt. Bestehende, per Oberfläche oder früherem Import angelegte Einträge laufen weiter.

## Änderungsprotokoll

Siehe [CHANGELOG.md](CHANGELOG.md).

## Danksagung

Ein herzliches **Dankeschön an [@rcasula](https://github.com/rcasula)**, den Autor der ursprünglichen Integration [kostalpiko-homeassistant](https://github.com/rcasula/kostalpiko-homeassistant). Ohne seine Arbeit gäbe es dieses Projekt nicht – es basiert auf seinem Code und seiner Idee, Kostal-Piko-Wechselrichter in Home Assistant zu bringen.

Das Auslesen der Wechselrichter-Seiten stammt aus der Bibliothek [`kostalpiko`](https://github.com/rcasula/kostalpiko) (MIT-Lizenz) und damit von **Tafkas** ([KostalPikoPy](https://github.com/Tafkas/KostalPikoPy)), **Giel Janssens** ([gieljnssns](https://github.com/gieljnssns/KostalPyko)) und den weiteren Mitwirkenden (maubreville, rcasula, britiger, Abildgren). Die Herkunft und der Lizenztext stehen in der Datei [NOTICE](NOTICE). Auch dafür herzlichen Dank!

Ebenso danke an [@m-rossi](https://github.com/m-rossi) für seine Beiträge zum Upstream-Projekt (Tagesenergie für das Energie-Dashboard, Anpassungen an neue Home-Assistant-Versionen, `state_class`/`device_class` der Sensoren) sowie an alle weiteren, die dort Fehler gemeldet und Verbesserungen beigetragen haben.

## Haftungsausschluss

Dies ist eine unabhängige, community-entwickelte Integration. Sie steht in keiner Verbindung zu Kostal und wird von dem Hersteller weder unterstützt noch empfohlen. Sie wird **„wie besehen“, ohne jegliche Gewährleistung** bereitgestellt; die Nutzung erfolgt auf eigenes Risiko. Die Integration liest nur Werte aus, schreibt aber nichts an den Wechselrichter.

## Markenhinweis

„Kostal“ und „Piko“ sowie alle sonstigen in diesem Repository genannten Produkt- und Firmennamen sind Marken oder eingetragene Marken ihrer jeweiligen Inhaber. Ihre Nennung dient ausschließlich der Beschreibung, mit welcher Hardware diese Integration kompatibel ist. „Home Assistant“ ist eine Marke der Open Home Foundation.

## Copyright & Lizenz

Copyright © 2026 bertel2020. Lizenziert unter der [MIT-Lizenz](LICENSE).

Ursprünglich entstanden aus [rcasula/kostalpiko-homeassistant](https://github.com/rcasula/kostalpiko-homeassistant) (siehe [Danksagung](#danksagung)). Das ursprüngliche Repository enthält keine Lizenzdatei.
