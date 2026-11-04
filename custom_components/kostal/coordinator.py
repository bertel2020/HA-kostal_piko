"""Data update coordinator for the Kostal Piko inverter."""

from __future__ import annotations

import logging
from collections import deque
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calculations import dc_power, windowed_efficiency
from .client import KostalAuthError, KostalClient, KostalError
from .const import (
    DOMAIN,
    EFFICIENCY_WINDOW,
    UNAVAILABLE_AFTER,
)

_LOGGER = logging.getLogger(__name__)


class KostalCoordinator(DataUpdateCoordinator):
    """Fetch all inverter values with a single request set per interval.

    A failed poll keeps the last values; after UNAVAILABLE_AFTER (about 90
    seconds, so 3 polls with the default interval) of failed polls in a row
    all entities become unavailable. The coordinator logs the failure once and the recovery once.
    Wrong credentials start a re-authentication immediately.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry,
        client: KostalClient,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self._failures = 0
        self._failure_limit = max(1, round(UNAVAILABLE_AFTER / update_interval))
        # (time, AC power, DC power) of the last EFFICIENCY_WINDOW
        self._samples: deque = deque()

    @property
    def efficiency(self) -> float | None:
        """Efficiency in percent, averaged over the last EFFICIENCY_WINDOW."""
        return windowed_efficiency([(ac, dc) for _, ac, dc in self._samples])

    def _record_sample(self, data) -> None:
        now = dt_util.utcnow()
        ac = data.get("current_power")
        dc = dc_power(data)
        if ac is not None and dc and dc > 0:
            self._samples.append((now, ac, dc))
        while self._samples and self._samples[0][0] < now - EFFICIENCY_WINDOW:
            self._samples.popleft()

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
            if self.data is None or self._failures >= self._failure_limit:
                raise UpdateFailed(f"Update of the inverter failed: {err}") from err
            _LOGGER.debug(
                "Poll %s of %s failed, keeping last values: %s",
                self._failures,
                self._failure_limit,
                err,
            )
            return self.data
        self._failures = 0
        self._record_sample(result["data"])
        return result
