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

def _dc_power(data):
    """Return the DC input power in W: sum of voltage * current of all strings.

    Returns None if the inverter reports no string values at all.
    """
    total = 0.0
    found = False
    for string in (1, 2, 3):
        voltage = getattr(data, f"get_string{string}_voltage")()
        current = getattr(data, f"get_string{string}_current")()
        if voltage is not None and current is not None:
            total += voltage * current
            found = True
    return round(total) if found else None


def _efficiency(data):
    """Return the inverter efficiency in percent (AC power / DC power).

    Returns None while there is no DC input (night), instead of a bogus 0 %.
    """
    ac = data.get_current_power()
    dc = _dc_power(data)
    if ac is None or not dc or dc <= 0:
        return None
    return round(ac / dc * 100, 1)


# sensor type -> (key in coordinator data, getter name or function)
VALUE_GETTERS = {
    "current_power": ("data", "get_current_power"),
    "total_energy": ("data", "get_total_energy"),
    "daily_energy": ("data", "get_daily_energy"),
    "string1_voltage": ("data", "get_string1_voltage"),
    "string1_current": ("data", "get_string1_current"),
    "string2_voltage": ("data", "get_string2_voltage"),
    "string2_current": ("data", "get_string2_current"),
    "string3_voltage": ("data", "get_string3_voltage"),
    "string3_current": ("data", "get_string3_current"),
    "l1_voltage": ("data", "get_l1_voltage"),
    "l1_power": ("data", "get_l1_power"),
    "l2_voltage": ("data", "get_l2_voltage"),
    "l2_power": ("data", "get_l2_power"),
    "l3_voltage": ("data", "get_l3_voltage"),
    "l3_power": ("data", "get_l3_power"),
    "status": ("data", "get_piko_status"),
    "solar_generator_power": ("ba_data", "get_solar_generator_power"),
    "consumption_phase_1": ("ba_data", "get_consumption_phase_1"),
    "consumption_phase_2": ("ba_data", "get_consumption_phase_2"),
    "consumption_phase_3": ("ba_data", "get_consumption_phase_3"),
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
            value = getter(obj) if callable(getter) else getattr(obj, getter)()
        except (AttributeError, IndexError, TypeError, ValueError) as err:
            _LOGGER.debug("Could not read %s: %s", self.type, err)
            return None
        # kostalpiko returns the text "No BA sensor installed" for the BA
        # values if the hardware is missing. Numeric sensors must not get text.
        if self._attr_native_unit_of_measurement is not None and isinstance(value, str):
            return None
        return value
