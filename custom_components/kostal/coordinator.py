"""Data update coordinator for the Kostal Piko inverter."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import KostalAuthError, KostalClient, KostalError
from .const import DOMAIN, FAILURES_BEFORE_UNAVAILABLE, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class KostalCoordinator(DataUpdateCoordinator):
    """Fetch all inverter values with a single request set per interval.

    A single failed poll keeps the last values; after
    FAILURES_BEFORE_UNAVAILABLE failed polls in a row all entities become
    unavailable. The coordinator logs the failure once and the recovery once.
    Wrong credentials start a re-authentication immediately.
    """

    def __init__(self, hass: HomeAssistant, entry, client: KostalClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.client = client
        self._failures = 0

    async def _async_fetch(self) -> dict:
        data = await self.client.async_get_data()

        # The BA sensor is optional; a problem there must not make the
        # inverter values unavailable, the last BA values are kept.
        ba_data = (self.data or {}).get("ba_data")
        try:
            ba_data = await self.client.async_get_ba_data()
        except KostalError as err:
            _LOGGER.debug("BA data not available: %s", err)
        return {"data": data, "ba_data": ba_data}

    async def _async_update_data(self):
        try:
            result = await self._async_fetch()
        except KostalAuthError as err:
            raise ConfigEntryAuthFailed("Invalid username or password") from err
        except KostalError as err:
            self._failures += 1
            if self.data is None or self._failures >= FAILURES_BEFORE_UNAVAILABLE:
                raise UpdateFailed(f"Inverter not reachable: {err}") from err
            _LOGGER.debug(
                "Poll %s of %s failed, keeping last values: %s",
                self._failures,
                FAILURES_BEFORE_UNAVAILABLE,
                err,
            )
            return self.data
        self._failures = 0
        return result
