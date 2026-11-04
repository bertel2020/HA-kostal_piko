"""Diagnostics support for Kostal Piko."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import KostalConfigEntry
from .sensor import VALUE_GETTERS

TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD, "unique_id", "serial_number"}


def _read(obj, getter) -> Any:
    """Read one value defensively, diagnostics must never fail."""
    if obj is None:
        return None
    try:
        return getter(obj) if callable(getter) else obj.get(getter)
    except Exception as err:  # noqa: BLE001
        return f"error: {err!r}"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KostalConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    data = coordinator.data or {}

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "inverter": async_redact_data(
            {"serial_number": runtime.serial_number, "model": runtime.model},
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "has_data": data.get("data") is not None,
            "has_ba_data": data.get("ba_data") is not None,
        },
        "values": {
            **{
                sensor_type: _read(data.get(source), getter)
                for sensor_type, (source, getter) in VALUE_GETTERS.items()
            },
            "efficiency": coordinator.efficiency,
            "average_power_15min": coordinator.average_power,
        },
    }
