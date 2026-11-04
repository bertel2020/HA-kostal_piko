"""The Kostal PIKO inverter sensor integration."""

import logging
from dataclasses import dataclass

from kostalpiko.kostalpiko import Piko

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .configuration_schema import CONFIG_SCHEMA, CONFIG_SCHEMA_ROOT  # noqa: F401
from .const import DOMAIN
from .coordinator import KostalCoordinator

_LOGGER = logging.getLogger(__name__)

__version__ = "2.1.0"
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


async def async_setup(hass, config):
    """Set up this integration using yaml."""
    _LOGGER.info("Setup kostal, %s", __version__)
    if DOMAIN not in config:
        return True

    data = dict(config.get(DOMAIN))
    hass.data["yaml_kostal"] = data

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config[DOMAIN])
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Set up KostalPiko from a config entry."""
    _LOGGER.info("Starting kostal, %s", __version__)

    if entry.source == "import":
        if entry.options:  # config.yaml
            data = entry.options.copy()
        elif "yaml_kostal" in hass.data:
            data = hass.data["yaml_kostal"]
        else:
            await hass.config_entries.async_remove(entry.entry_id)
            return False
    else:
        data = entry.data.copy()
        data.update(entry.options)

    conf = CONFIG_SCHEMA_ROOT(data)

    piko = Piko(conf[CONF_HOST], conf[CONF_USERNAME], conf[CONF_PASSWORD])

    # The serial number is part of the unique_id of every entity, so it has
    # to be known before any sensor is created. If the inverter is not
    # reachable (e.g. at night) Home Assistant retries automatically.
    try:
        info = await hass.async_add_executor_job(piko._get_info)
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(f"Cannot read inverter info: {err}") from err
    if not info or len(info) < 2:
        raise ConfigEntryNotReady("Kostal inverter not reachable")

    coordinator = KostalCoordinator(hass, entry, piko)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = KostalRuntimeData(
        coordinator=coordinator,
        serial_number=info[0],
        model=info[1],
        monitored_conditions=conf[CONF_MONITORED_CONDITIONS],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
