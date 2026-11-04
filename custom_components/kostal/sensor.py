"""Support for Kostal PIKO Photvoltaic (PV) inverter."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KostalConfigEntry
from .const import DOMAIN, SENSOR_TYPES
from .coordinator import KostalCoordinator

_LOGGER = logging.getLogger(__name__)

# The coordinator bundles all requests, entities never poll on their own.
PARALLEL_UPDATES = 0

def _string_power(data, string):
    """Return the power of one string in W (voltage * current), or None."""
    voltage = data.get(f"string{string}_voltage")
    current = data.get(f"string{string}_current")
    if voltage is None or current is None:
        return None
    return round(voltage * current)


def _dc_power(data):
    """Return the DC input power in W: sum of the power of all strings.

    Returns None if the inverter reports no string values at all.
    """
    powers = [_string_power(data, string) for string in (1, 2, 3)]
    powers = [power for power in powers if power is not None]
    return sum(powers) if powers else None


def _efficiency(data):
    """Return the inverter efficiency in percent (AC power / DC power).

    Returns None while there is no DC input (standby), instead of a bogus 0 %.
    """
    ac = data.get("current_power")
    dc = _dc_power(data)
    if ac is None or not dc or dc <= 0:
        return None
    return round(ac / dc * 100, 1)


# sensor type -> (key in coordinator data, value name or function)
_DATA_SENSORS = (
    "current_power", "total_energy", "daily_energy",
    "string1_voltage", "string1_current", "string2_voltage", "string2_current",
    "string3_voltage", "string3_current",
    "l1_voltage", "l1_power", "l2_voltage", "l2_power", "l3_voltage", "l3_power",
    "status",
)  # fmt: skip
_BA_SENSORS = (
    "solar_generator_power", "consumption_phase_1", "consumption_phase_2", "consumption_phase_3",
)  # fmt: skip
VALUE_GETTERS = {
    **{name: ("data", name) for name in _DATA_SENSORS},
    **{name: ("ba_data", name) for name in _BA_SENSORS},
    "string1_power": ("data", lambda data: _string_power(data, 1)),
    "string2_power": ("data", lambda data: _string_power(data, 2)),
    "string3_power": ("data", lambda data: _string_power(data, 3)),
    "dc_power": ("data", _dc_power),
    "efficiency": ("data", _efficiency),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KostalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kostal sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        PikoSensor(runtime.coordinator, runtime, sensor_type, entry.title)
        for sensor_type in runtime.monitored_conditions
    )


class PikoSensor(CoordinatorEntity[KostalCoordinator], SensorEntity):
    """Representation of a Piko inverter value."""

    def __init__(self, coordinator: KostalCoordinator, runtime, sensor_type, title) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        _LOGGER.debug("Initializing PikoSensor: %s", sensor_type)
        name, unit, icon, state_class, device_class = SENSOR_TYPES[sensor_type]
        self.type = sensor_type
        self._sensor = name

        # name and unique_id are deliberately unchanged compared to earlier
        # versions, so existing entities (entity_id, history, statistics)
        # are kept when the integration is replaced.
        self._attr_name = "{} {}".format(title, name)
        self._attr_unique_id = "{} {}".format(runtime.serial_number, name)
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        if unit is not None:
            self._attr_state_class = SensorStateClass(state_class)
            if device_class is not None:
                self._attr_device_class = SensorDeviceClass(device_class)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.serial_number)},
            name=title,
            manufacturer="Kostal",
            model=runtime.model,
        )

    @property
    def native_value(self):
        """Return the value of the sensor."""
        source, getter = VALUE_GETTERS[self.type]
        obj = (self.coordinator.data or {}).get(source)
        if obj is None:
            return None
        try:
            value = getter(obj) if callable(getter) else obj.get(getter)
        except (AttributeError, IndexError, TypeError, ValueError) as err:
            _LOGGER.debug("Could not read %s: %s", self.type, err)
            return None
        # Numeric sensors must never get text as state.
        if self._attr_native_unit_of_measurement is not None and isinstance(value, str):
            return None
        return value
