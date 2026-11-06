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
from .calculations import dc_power, specific_yield, string_power, utilization
from .const import DOMAIN, SENSOR_TYPES
from .coordinator import KostalCoordinator

_LOGGER = logging.getLogger(__name__)

# The coordinator bundles all requests, entities never poll on their own.
PARALLEL_UPDATES = 0

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
    "string1_power": ("data", lambda data: string_power(data, 1)),
    "string2_power": ("data", lambda data: string_power(data, 2)),
    "string3_power": ("data", lambda data: string_power(data, 3)),
    "dc_power": ("data", dc_power),
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
        self._runtime = runtime
        self._sensor = name

        # unique_id and entity_id are deliberately unchanged compared to earlier
        # versions, so existing entities (entity_id, history, statistics)
        # are kept when the integration is replaced. Only the displayed name
        # is translated.
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_type
        self._object_id = name  # english, HA puts the device name in front
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
    def suggested_object_id(self) -> str:
        """Keep the entity_id independent of the language of the name (HA adds the device name)."""
        return self._object_id

    @property
    def native_value(self):
        """Return the value of the sensor."""
        if self.type == "efficiency":  # averaged over several polls
            return self.coordinator.efficiency
        if self.type == "average_power_15min":  # mean of the last polls
            return self.coordinator.average_power
        if self.type == "utilization":  # needs the plant data
            return utilization(
                (self.coordinator.data or {}).get("data", {}).get("current_power"),
                self._runtime.max_output_power,
            )
        if self.type == "specific_yield":
            return specific_yield(
                (self.coordinator.data or {}).get("data", {}).get("daily_energy"),
                self._runtime.string_wp.values(),
            )
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
