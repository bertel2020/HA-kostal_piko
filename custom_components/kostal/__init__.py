"""The Kostal PIKO inverter sensor integration."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import KostalAuthError, KostalClient, KostalError
from .configuration_schema import CONFIG_SCHEMA_ROOT
from .coordinator import KostalCoordinator

_LOGGER = logging.getLogger(__name__)

__version__ = "2.2.0"
VERSION = __version__

PLATFORMS = ["sensor"]


@dataclass
class KostalRuntimeData:
    """Runtime data of a config entry."""

    coordinator: KostalCoordinator
    serial_number: str
    model: str
    monitored_conditions: list[str]


type KostalConfigEntry = ConfigEntry[KostalRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Set up KostalPiko from a config entry."""
    _LOGGER.info("Starting kostal, %s", __version__)

    data = dict(entry.data)
    data.update(entry.options)

    conf = CONFIG_SCHEMA_ROOT(data)

    client = KostalClient(
        async_get_clientsession(hass),
        conf[CONF_HOST],
        conf[CONF_USERNAME],
        conf[CONF_PASSWORD],
    )

    # The serial number is part of the unique_id of every entity, so it has
    # to be known before any sensor is created. If the inverter is not
    # reachable Home Assistant retries automatically.
    try:
        info = await client.async_get_info()
    except KostalAuthError as err:
        raise ConfigEntryAuthFailed("Invalid username or password") from err
    except KostalError as err:
        raise ConfigEntryNotReady(f"Cannot read inverter info: {err}") from err

    # Entries created by older versions have no unique_id. Add it, so the
    # config flow can detect duplicates. Entities are not affected.
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=info.serial_number)

    coordinator = KostalCoordinator(
        hass, entry, client, timedelta(seconds=conf[CONF_SCAN_INTERVAL])
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = KostalRuntimeData(
        coordinator=coordinator,
        serial_number=info.serial_number,
        model=info.model,
        monitored_conditions=conf[CONF_MONITORED_CONDITIONS],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
