# Changelog

*[🇩🇪 Deutsche Version](CHANGELOG.md)*

All notable changes to this project are documented here.
Versions follow the `version` field in `custom_components/kostal/manifest.json`.

## 2.2.0 – 2026-11-04

**New**
- **Own client** (`client.py`) instead of the `kostalpiko` library: asynchronous through Home Assistant's HTTP connection, without private methods and without a version limit. Reading the pages is based on `kostalpiko` (MIT, see [NOTICE](NOTICE)). Tested with sample pages of five layouts and the pages of a real PIKO 10.1.
- **Wrong passwords are detected** (HTTP 401): setup shows "Invalid username or password", during operation Home Assistant starts a **re-authentication** instead of logging errors forever.
- **Script `scripts/check_inverter.py`** reads an inverter with the client and prints all values (the password is asked for).

**New (continued)**
- **Adjustable update interval** (10 to 600 seconds, default 30) via **Configure**. The time until "unavailable" stays at about 90 seconds regardless of the interval.

**Changed**
- **Sensor names translated** (German and English, e.g. "Aktuelle Leistung"). Only the displayed name changes, entity IDs and `unique_id` stay the same, also for new installations with a German interface. Names you set yourself are kept.
- **Unsupported inverters** are reported clearly during setup ("This inverter is not supported", with a hint to open an issue) instead of "could not connect". For this the setup also reads the main page. The log message of a failed update no longer claims that the inverter is unreachable.
- **Efficiency smoothed:** It is averaged over the last 5 minutes (sum AC ÷ sum DC) instead of being calculated from a single poll, which varied by several percent when the irradiation changed.
- Dependency `lxml` instead of `kostalpiko`. Minimum Home Assistant **2025.8.0** (the options flow reloads the integration itself).
- An unknown page structure (different number of values) is reported as an error instead of silently returning "unknown".
- The BA sensors show the values returned by the inverter (e.g. 0 W) instead of the text "No BA sensor installed".

## 2.1.0 – 2026-11-04

**New**
- **Calculated sensors:** *String 1/2/3 power* (voltage × current per string), *DC power* (sum) and *Efficiency* (AC ÷ DC in %). They replace matching template sensors. Without DC input (standby) efficiency is "unknown" instead of 0 %.
- **Reconfigure:** host and credentials can be changed without deleting the integration (rejected for a different serial number). Entities and history are kept.
- **Diagnostics download** (host, username, password and serial number redacted) and `PARALLEL_UPDATES`.
- **Options flow:** The monitored sensors can be changed afterwards via **Configure** without deleting the integration. Entity IDs are kept.
- **Translations:** German and English for setup, options and error messages.
- **Tests:** Automated tests against Home Assistant 2026.10.4 (config flow, options flow, setup, unload/reload, preservation of existing entities, calculations).

**Changed**
- **Outages are detected:** After three failed polls in a row (~1.5 minutes) the sensors become "unavailable" instead of showing stale values; outage and recovery are each logged once. The `kostalpiko` library swallows network errors, so the inverter pages are now requested directly (`kostalpiko` limited to `>=0.6,<0.7`). Before this change sensors kept showing the last value during an outage.
- **Shared `DataUpdateCoordinator`** (30 s) instead of a throttled request per sensor. The sensors use the native sensor API (`native_value`, `native_unit_of_measurement`) with a real `device_class` and `state_class` instead of attributes. Entity ID, name, `unique_id` and device are unchanged.
- **Setup at startup:** If the inverter is unreachable, Home Assistant retries automatically. Before, the integration stayed without sensors until reloaded manually.
- **Serial number as entry identifier:** the same inverter cannot be added twice. Existing entries receive it on their next start.
- **Metadata:** `iot_class: local_polling`, `integration_type: device`, correct documentation and issue links; minimum Home Assistant 2024.12.0.

**Fixed**
- **Connection check in the config flow** detected neither an unreachable inverter nor wrong credentials and created the entry anyway.
- **Stuck updates:** a single network error could block all further updates until restart.
- **Reload/unload:** the sensor platform was not unloaded; reloading could create duplicate entities.
- **BA sensors** returned the text "No BA sensor installed" as the state of power sensors; now "unknown".
- Error in the host check for entries without a host in their data.

**Removed**
- The YAML setup via a `kostal:` block in `configuration.yaml`. Existing entries keep working.
