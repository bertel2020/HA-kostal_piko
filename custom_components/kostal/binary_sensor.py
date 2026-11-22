"""Problem binary sensor of the Kostal Piko inverter."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KostalConfigEntry
from .const import DOMAIN
from .coordinator import KostalCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KostalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the problem sensor."""
    runtime = entry.runtime_data
    async_add_entities([PikoProblemSensor(runtime.coordinator, runtime, entry.title)])


class PikoProblemSensor(CoordinatorEntity[KostalCoordinator], BinarySensorEntity):
    """On while the inverter has not answered for a longer time.

    Use it in an automation to get a notification of an outage; the same
    condition raises the repair issue.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: KostalCoordinator, runtime, title) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{runtime.serial_number} Problem"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.serial_number)},
            name=title,
            manufacturer="Kostal",
            model=runtime.model,
        )

    @property
    def available(self) -> bool:
        """Stay available during an outage, that is exactly when it matters."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True during an outage."""
        return self.coordinator.outage
