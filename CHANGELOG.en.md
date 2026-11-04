# Changelog

*[🇩🇪 Deutsche Version](CHANGELOG.md)*

All notable changes to this project are documented here.
Versions follow the `version` field in `custom_components/kostal/manifest.json`.

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
