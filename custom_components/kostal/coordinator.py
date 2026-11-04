"""Data update coordinator for the Kostal Piko inverter."""

import logging

from kostalpiko.kostalpiko import Piko, PikoBAData, PikoData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FAILURES_BEFORE_UNAVAILABLE, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class KostalCoordinator(DataUpdateCoordinator):
    """Fetch all inverter values with a single request set per interval.

    The kostalpiko library swallows connection errors and silently keeps the
    old values, which would show stale values during an outage. Therefore the
    raw pages are requested here directly, so that a failure is detected.

    A single failed poll keeps the last values; after
    FAILURES_BEFORE_UNAVAILABLE failed polls in a row all entities become
    unavailable. The coordinator logs the failure once and the recovery once.
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
        self._failures = 0

    def _fetch(self) -> dict:
        """Request the inverter (blocking, runs in the executor)."""
        raw = self.piko._get_raw_content()
        if raw is None:
            raise ConnectionError("no response from the inverter")
        data = PikoData(raw)

        # The BA sensor is optional; a problem there must not make the
        # inverter values unavailable, the last BA values are kept.
        ba_data = (self.data or {}).get("ba_data")
        try:
            raw_ba = self.piko._get_content_of_own_consumption()
            if raw_ba is not None:
                ba_data = PikoBAData(raw_ba)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("BA data not available: %s", err)
        return {"data": data, "ba_data": ba_data}

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(self._fetch)
        except Exception as err:  # noqa: BLE001
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
