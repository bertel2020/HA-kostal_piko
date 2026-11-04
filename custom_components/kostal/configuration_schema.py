"""Kostal Piko Configuration Schemas."""

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL,
)

import homeassistant.helpers.config_validation as cv

from .const import (
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_TYPES,
)

CONFIG_SCHEMA_ROOT = vol.Schema({
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
})
