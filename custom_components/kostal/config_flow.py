"""Adds config flow for Kostal."""

import logging
from dataclasses import dataclass

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
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .calculations import available_sensors
from .client import (
    KostalAuthError,
    KostalClient,
    KostalError,
    KostalParseError,
    PikoInfo,
)
from .const import (
    CONF_MAX_OUTPUT_POWER,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ISSUES_URL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_TYPES,
    STRINGS,
    string_wp_key,
)

SUPPORTED_SENSOR_TYPES = list(SENSOR_TYPES)


@dataclass
class Detected:
    """What the inverter reported during the connection check."""

    info: PikoInfo
    sensors: list[str]


# The sensors in the order and groups of the selection form. Every group is a
# section of the form, the stored value is still one flat list.
SENSOR_GROUPS: dict[str, list[str]] = {
    "power": [
        "current_power", "daily_energy", "total_energy",
        "average_power_15min", "efficiency", "status",
        "utilization", "specific_yield",
    ],
    "dc": [
        "dc_power",
        "string1_power", "string1_voltage", "string1_current",
        "string2_power", "string2_voltage", "string2_current",
        "string3_power", "string3_voltage", "string3_current",
    ],
    "ac": [
        "l1_voltage", "l1_power", "l2_voltage", "l2_power", "l3_voltage", "l3_power",
    ],
    "ba": [
        "solar_generator_power",
        "consumption_phase_1", "consumption_phase_2", "consumption_phase_3",
    ],
}  # fmt: skip


async def sensor_schema(hass: HomeAssistant, selected) -> dict:
    """Return the schema fields for the sensor selection (one section per group).

    The labels are looked up here instead of by the frontend, so they are also
    shown when the browser has cached the translations of an older version.
    """
    labels = await async_get_translations(
        hass, hass.config.language, "entity", [DOMAIN]
    )
    fields = {}
    for group, names in SENSOR_GROUPS.items():
        options = [
            SelectOptionDict(
                value=name,
                label=labels.get(
                    f"component.{DOMAIN}.entity.sensor.{name}.name",
                    SENSOR_TYPES[name][0],
                ),
            )
            for name in names
        ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=options, multiple=True, mode=SelectSelectorMode.LIST
            )
        )
        fields[vol.Required(group)] = section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_MONITORED_CONDITIONS,
                        default=[name for name in names if name in selected],
                    ): selector
                }
            ),
            {"collapsed": False},
        )
    return fields


def plant_schema(strings, defaults=None) -> dict:
    """Return the optional plant fields: installed power per string, max. output."""
    defaults = defaults or {}

    def number(unit):
        return NumberSelector(
            NumberSelectorConfig(
                min=0, max=1000000, step=1, unit_of_measurement=unit,
                mode=NumberSelectorMode.BOX,
            )
        )

    def optional(key):
        value = defaults.get(key)
        suggested = {"suggested_value": value} if value else None
        return vol.Optional(key, description=suggested)

    fields = {optional(string_wp_key(n)): number("Wp") for n in strings}
    fields[optional(CONF_MAX_OUTPUT_POWER)] = number("W")
    return fields


def plant_values(user_input: dict, strings) -> dict:
    """Return the plant values as integers; empty fields become 0 (= not set)."""
    keys = [string_wp_key(n) for n in strings] + [CONF_MAX_OUTPUT_POWER]
    return {key: int(user_input.get(key) or 0) for key in keys}


def derived_sensors(values: dict) -> list[str]:
    """Return the sensors that need plant values, for the values that are set."""
    found = []
    if values.get(CONF_MAX_OUTPUT_POWER):
        found.append("utilization")
    if any(values.get(string_wp_key(n)) for n in STRINGS):
        found.append("specific_yield")
    return found


def flatten_sensors(user_input: dict) -> list[str]:
    """Return the selected sensors of all sections as one list."""
    selected: list[str] = []
    for group in SENSOR_GROUPS:
        selected.extend(user_input.get(group, {}).get(CONF_MONITORED_CONDITIONS, []))
    return selected


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
) -> tuple[Detected | None, str | None]:
    """Try to read the inverter. Returns (detected, None) or (None, error key)."""
    client = KostalClient(async_get_clientsession(hass), host, username, password)
    try:
        info = await client.async_get_info()
        # also read the main page: it shows whether the page layout of this
        # inverter is known
        data = await client.async_get_data()
        try:
            ba_data = await client.async_get_ba_data()
        except KostalError:
            ba_data = None  # optional, not every inverter has the BA page
        found = available_sensors(data, ba_data)
        return Detected(info, [name for name in SUPPORTED_SENSOR_TYPES if name in found]), None
    except KostalAuthError:
        return None, "invalid_auth"
    except KostalParseError as err:
        _LOGGER.warning("Unsupported inverter pages at %s: %s", host, err)
        return None, "unsupported_device"
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
        self._name = DEFAULT_NAME
        self._connection: dict = {}
        self._sensors: list[str] = []
        self._selected: list[str] = []

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if the host is already configured."""
        return host in kostal_entries(self.hass)

    async def async_step_user(self, user_input=None):
        """Ask for the connection data."""
        self._errors = {}

        if user_input is not None:
            if self._host_in_configuration_exists(user_input[CONF_HOST]):
                self._errors[CONF_HOST] = "host_exists"
            else:
                detected, error = await async_check_connection(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                if error is not None:
                    self._errors["base"] = error
                else:
                    # The serial number identifies the inverter, regardless of
                    # how the host URL is spelled.
                    await self.async_set_unique_id(detected.info.serial_number)
                    self._abort_if_unique_id_configured()
                    self._name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
                    self._connection = {
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    self._sensors = detected.sensors
                    return await self.async_step_sensors()
        else:
            user_input = {CONF_NAME: DEFAULT_NAME, CONF_HOST: "http://"}

        setup_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                ): str,
                vol.Required(
                    CONF_HOST, default=user_input.get(CONF_HOST, "http://")
                ): str,
                vol.Required(
                    CONF_USERNAME,
                    default=user_input.get(CONF_USERNAME, "pvserver"),
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=setup_schema,
            errors=self._errors,
            description_placeholders={"issues_url": ISSUES_URL},
        )

    async def async_step_sensors(self, user_input=None):
        """Choose the sensors; all that this inverter provides are preselected."""
        if user_input is not None:
            self._selected = flatten_sensors(user_input)
            return await self.async_step_plant()

        schema = vol.Schema(await sensor_schema(self.hass, self._sensors))
        return self.async_show_form(step_id="sensors", data_schema=schema)

    async def async_step_plant(self, user_input=None):
        """Optional plant data: installed power per string and max. output power.

        A string without a value counts as unused.
        """
        strings = [n for n in STRINGS if f"string{n}_power" in self._sensors]
        if user_input is not None:
            values = plant_values(user_input, strings)
            sensors = self._selected + [
                name for name in derived_sensors(values) if name not in self._selected
            ]
            return self.async_create_entry(
                title=self._name,
                data={
                    **self._connection,
                    CONF_MONITORED_CONDITIONS: sensors,
                    **values,
                },
            )

        return self.async_show_form(
            step_id="plant", data_schema=vol.Schema(plant_schema(strings))
        )

    async def async_step_reconfigure(self, user_input=None):
        """Change host and credentials of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            detected, error = await async_check_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is not None:
                errors["base"] = error
            elif entry.unique_id and detected.info.serial_number != entry.unique_id:
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
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={"issues_url": ISSUES_URL},
        )

    async def async_step_reauth(self, entry_data):
        """Start re-authentication after the inverter rejected the login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            detected, error = await async_check_connection(
                self.hass,
                entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is not None:
                errors["base"] = error
            elif entry.unique_id and detected.info.serial_number != entry.unique_id:
                return self.async_abort(reason="wrong_device")
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        current = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "host": entry.data[CONF_HOST],
                "issues_url": ISSUES_URL,
            },
        )


class KostalOptionsFlow(config_entries.OptionsFlowWithReload):
    """Allow changing the monitored sensors of an existing entry."""

    async def async_step_init(self, user_input=None):
        """Manage the monitored sensors."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_MONITORED_CONDITIONS: flatten_sensors(user_input),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    **plant_values(user_input, STRINGS),
                }
            )

        current = self.config_entry.options.get(
            CONF_MONITORED_CONDITIONS,
            self.config_entry.data.get(CONF_MONITORED_CONDITIONS, []),
        )
        interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        plant = {
            key: self.config_entry.options.get(key, self.config_entry.data.get(key))
            for key in (CONF_MAX_OUTPUT_POWER, *(string_wp_key(n) for n in STRINGS))
        }
        schema = vol.Schema(
            {
                **await sensor_schema(self.hass, current),
                **plant_schema(STRINGS, plant),
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
