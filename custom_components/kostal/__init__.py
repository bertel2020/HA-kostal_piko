"""The Kostal PIKO inverter sensor integration."""

import logging

from .piko_holder import PikoHolder

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

from .const import DEFAULT_NAME, DOMAIN, SENSOR_TYPES
from .configuration_schema import CONFIG_SCHEMA, CONFIG_SCHEMA_ROOT

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    EVENT_HOMEASSISTANT_STOP
)

_LOGGER = logging.getLogger(__name__)

__version__ = "2.0.0"
VERSION = __version__


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Setup KostalPiko component"""

    _LOGGER.info("Starting kostal, %s", __version__)

    if not DOMAIN in hass.data:
        hass.data[DOMAIN] = {}

    if entry.source == "import":
        if entry.options:  # config.yaml
            data = entry.options.copy()
        else:
            if "yaml_kostal" in hass.data:
                data = hass.data["yaml_kostal"]
            else:
                data = {}
                await hass.config_entries.async_remove(entry.entry_id)
    else:
        data = entry.data.copy()
        data.update(entry.options)

    conf = CONFIG_SCHEMA_ROOT(data)

    hass.data[DOMAIN][entry.entry_id] = KostalInstance(hass, entry, conf)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    instance = hass.data[DOMAIN].get(entry.entry_id)
    if instance is None:
        return True

    unload_ok = True
    if instance.platforms_loaded:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        await instance.stop()
        await instance.clean()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


class KostalInstance():
    """Config instance of Kostal"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, conf):
        self.hass = hass
        self.config_entry = entry
        self.entry_id = self.config_entry.entry_id
        self.conf = conf
        self.piko = PikoHolder(
            conf[CONF_HOST], conf[CONF_USERNAME], conf[CONF_PASSWORD]
        )

        self.platforms_loaded = False

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        )

        self._startup_task = entry.async_create_background_task(
            hass, self.start_up(), f"kostal start_up {self.entry_id}"
        )

    @property
    def signal_init_sensors(self) -> str:
        """Dispatcher signal, unique per config entry."""
        return f"kostal_init_sensors_{self.entry_id}"

    async def start_up(self):
        try:
            await self.hass.async_add_executor_job(self.piko.update)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Initial update of Kostal inverter failed")
            return
        await self._asyncadd_sensors(self.conf[CONF_MONITORED_CONDITIONS], self.piko)

    async def stop(self, _=None):
        """Stop Kostal."""
        _LOGGER.info("Shutting down Kostal")

    async def _asyncadd_sensors(self, sensors, piko: PikoHolder):
        await self.hass.config_entries.async_forward_entry_setups(self.config_entry, ["sensor"])
        self.platforms_loaded = True
        async_dispatcher_send(self.hass, self.signal_init_sensors, sensors, piko)

    async def clean(self):
        pass
