"""The Kostal PIKO inverter sensor integration."""

import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import KostalAuthError, KostalClient, KostalError
from .const import (
    CONF_MAX_OUTPUT_POWER,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_TYPES,
    STRINGS,
    string_wp_key,
)
from .coordinator import KostalCoordinator

_LOGGER = logging.getLogger(__name__)

__version__ = "2.6.1"

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = f"/{DOMAIN}/kostal-piko-card.js"
CARD_FILE = Path(__file__).parent / "www" / "kostal-piko-card.js"

# Validates data and options of a config entry (older entries may still
# carry a name).
ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(list(SENSOR_TYPES))]
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
        # plant data, 0 = not set
        **{
            vol.Optional(key, default=0): vol.All(vol.Coerce(int), vol.Range(min=0))
            for key in (CONF_MAX_OUTPUT_POWER, *(string_wp_key(n) for n in STRINGS))
        },
    }
)


@dataclass
class KostalRuntimeData:
    """Runtime data of a config entry."""

    coordinator: KostalCoordinator
    serial_number: str
    model: str
    monitored_conditions: list[str]
    # installed power per string in Wp (0 = unused) and max. AC output in W (0 = not set)
    string_wp: dict[int, int] = field(default_factory=dict)
    max_output_power: int = 0


type KostalConfigEntry = ConfigEntry[KostalRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the Lovelace card of the integration and load it in the frontend."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    # the version in the URL makes browsers load a new card after an update
    add_extra_js_url(hass, f"{CARD_URL}?v={__version__}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Set up KostalPiko from a config entry."""
    _LOGGER.info("Starting kostal, %s", __version__)

    data = dict(entry.data)
    data.update(entry.options)

    conf = ENTRY_SCHEMA(data)

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
        string_wp={n: conf[string_wp_key(n)] for n in STRINGS},
        max_output_power=conf[CONF_MAX_OUTPUT_POWER],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KostalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
