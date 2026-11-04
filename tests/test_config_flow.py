"""Tests for the config and options flow."""
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kostal.const import DOMAIN

USER_INPUT = {
    "name": "Kostal Piko",
    "host": "http://192.168.1.50",
    "username": "pvserver",
    "password": "pvwr",
    "monitored_conditions": ["current_power", "efficiency"],
}


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(hass, fake_piko):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "kostal_piko"
    assert result["data"]["host"] == "http://192.168.1.50"
    assert result["result"].unique_id == "SN123"


async def test_unreachable_inverter_shows_error(hass, fake_piko):
    fake_piko.info = None  # kostalpiko returns None on errors and wrong passwords
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "could_not_connect"}


async def test_same_inverter_cannot_be_added_twice(hass, fake_piko):
    MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", data={"host": "http://other"}
    ).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_host_shows_error(hass, fake_piko):
    MockConfigEntry(domain=DOMAIN, data={"host": USER_INPUT["host"]}).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"host": "host_exists"}


async def test_options_flow_changes_sensors(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123",
        title="kostal_piko",
        data={**USER_INPUT, "monitored_conditions": ["current_power"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"monitored_conditions": ["current_power", "dc_power"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["monitored_conditions"] == ["current_power", "dc_power"]
