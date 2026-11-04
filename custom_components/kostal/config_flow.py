"""Adds config flow for Kostal."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.util import slugify

from .client import KostalAuthError, KostalClient, KostalError, PikoInfo
from .const import (
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_TYPES,
)

SUPPORTED_SENSOR_TYPES = list(SENSOR_TYPES)

DEFAULT_MONITORED_CONDITIONS = [
    "current_power",
    "total_energy",
    "daily_energy",
    "status",
]

_LOGGER = logging.getLogger(__name__)


@callback
def kostal_entries(hass: HomeAssistant):
    """Return the hosts for the domain."""
    hosts = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        host = entry.data.get(CONF_HOST) or entry.options.get(CONF_HOST)
        if host:
            hosts.add(host)
    return hosts


async def async_check_connection(
    hass: HomeAssistant, host: str, username: str, password: str
) -> tuple[PikoInfo | None, str | None]:
    """Try to read the inverter. Returns (info, None) or (None, error key)."""
    client = KostalClient(async_get_clientsession(hass), host, username, password)
    try:
        return await client.async_get_info(), None
    except KostalAuthError:
        return None, "invalid_auth"
    except KostalError as err:
        _LOGGER.debug("Cannot connect to %s: %s", host, err)
        return None, "could_not_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error while connecting to Kostal inverter")
        return None, "could_not_connect"


class KostalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kostal piko."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow to change the monitored sensors."""
        return KostalOptionsFlow()

    def __init__(self):
        """Initialize."""
        self._errors = {}

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if the host is already configured."""
        return host in kostal_entries(self.hass)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            if self._host_in_configuration_exists(user_input[CONF_HOST]):
                self._errors[CONF_HOST] = "host_exists"
            else:
                host = user_input[CONF_HOST]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                conditions = user_input[CONF_MONITORED_CONDITIONS]
                info, error = await async_check_connection(
                    self.hass, host, username, password
                )
                if error is not None:
                    self._errors["base"] = error
                else:
                    # The serial number identifies the inverter, regardless of
                    # how the host URL is spelled.
                    await self.async_set_unique_id(info.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_HOST: host,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_MONITORED_CONDITIONS: conditions,
                        },
                    )
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = "http://"
            user_input[CONF_USERNAME] = ""
            user_input[CONF_PASSWORD] = ""
            user_input[CONF_MONITORED_CONDITIONS] = DEFAULT_MONITORED_CONDITIONS

        default_monitored_conditions = (
            [] if self._async_current_entries() else DEFAULT_MONITORED_CONDITIONS
        )
        setup_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                ): str,
                vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                vol.Required(
                    CONF_USERNAME, description={"suggested_value": "pvserver"}
                ): str,
                vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                vol.Required(
                    CONF_MONITORED_CONDITIONS, default=default_monitored_conditions
                ): cv.multi_select(SUPPORTED_SENSOR_TYPES),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=setup_schema, errors=self._errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Change host and credentials of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            info, error = await async_check_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is not None:
                errors["base"] = error
            elif entry.unique_id and info.serial_number != entry.unique_id:
                return self.async_abort(reason="wrong_device")
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        current = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "http://")): str,
                vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def async_step_reauth(self, entry_data):
        """Start re-authentication after the inverter rejected the login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            info, error = await async_check_connection(
                self.hass,
                entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is not None:
                errors["base"] = error
            elif entry.unique_id and info.serial_number != entry.unique_id:
                return self.async_abort(reason="wrong_device")
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        current = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": entry.data[CONF_HOST]},
        )


class KostalOptionsFlow(config_entries.OptionsFlowWithReload):
    """Allow changing the monitored sensors of an existing entry."""

    async def async_step_init(self, user_input=None):
        """Manage the monitored sensors."""
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_MONITORED_CONDITIONS,
            self.config_entry.data.get(CONF_MONITORED_CONDITIONS, []),
        )
        interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MONITORED_CONDITIONS, default=list(current)
                ): cv.multi_select(SUPPORTED_SENSOR_TYPES),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
