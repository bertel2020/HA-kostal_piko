"""Data update coordinator for the Kostal Piko inverter."""

import logging

from kostalpiko.kostalpiko import Piko

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class KostalCoordinator(DataUpdateCoordinator):
    """Fetch all inverter values with a single request set per interval.

    The kostalpiko library swallows connection errors and keeps the last
    known values (the inverter is unreachable at night). This behaviour is
    kept on purpose: sensors keep their last value instead of turning
    unavailable.
    """

    def __init__(self, hass: HomeAssistant, entry, piko: Piko) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.piko = piko

    async def _async_update_data(self):
        await self.hass.async_add_executor_job(self.piko.update)
        return {"data": self.piko.data, "ba_data": self.piko.ba_data}
