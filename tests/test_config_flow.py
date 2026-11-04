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


CONNECTION = {k: v for k, v in USER_INPUT.items() if k != "monitored_conditions"}

# what the fake inverter provides (one phase, three strings, no BA hardware)
DETECTED = [
    "current_power", "total_energy", "daily_energy",
    "string1_voltage", "string1_current", "string2_voltage", "string2_current",
    "string3_voltage", "string3_current", "l1_voltage", "l1_power", "status",
    "string1_power", "string2_power", "string3_power", "dc_power", "efficiency",
    "average_power_15min",
]  # fmt: skip


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(hass, fake_piko):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monitored_conditions": ["current_power", "efficiency"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "kostal_piko"
    assert result["data"]["host"] == "http://192.168.1.50"
    assert result["data"]["monitored_conditions"] == ["current_power", "efficiency"]
    assert result["result"].unique_id == "SN123"


async def test_sensors_are_preselected_from_the_inverter(hass, fake_piko):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    # the defaults of the form are the preselection
    assert result["data_schema"]({})["monitored_conditions"] == DETECTED


async def test_ba_sensors_are_preselected_with_ba_values(hass, fake_piko):
    fake_piko.ba_values = {
        "solar_generator_power": 120,
        "consumption_phase_1": 50,
        "consumption_phase_2": 0,
        "consumption_phase_3": 10,
    }
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    selected = result["data_schema"]({})["monitored_conditions"]
    assert set(selected) == set(DETECTED) | {
        "solar_generator_power",
        "consumption_phase_1",
        "consumption_phase_2",
        "consumption_phase_3",
    }


async def test_failing_ba_page_does_not_break_setup(hass, fake_piko):
    fake_piko.ba_fail = True
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["step_id"] == "sensors"
    assert result["data_schema"]({})["monitored_conditions"] == DETECTED


async def test_sensors_follow_the_page_layout(hass, fake_piko):
    # two strings, no third string and no calculated string 3 power
    fake_piko.data_values = {"string3_voltage": None, "string3_current": None}
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    selected = result["data_schema"]({})["monitored_conditions"]
    assert "string2_power" in selected
    assert "string3_voltage" not in selected
    assert "string3_power" not in selected


async def test_unreachable_inverter_shows_error(hass, fake_piko):
    fake_piko.info = None  # the inverter does not answer
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "could_not_connect"}


async def test_same_inverter_cannot_be_added_twice(hass, fake_piko):
    MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", data={"host": "http://other"}
    ).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_host_shows_error(hass, fake_piko):
    MockConfigEntry(domain=DOMAIN, data={"host": USER_INPUT["host"]}).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
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


async def _reconfigure(hass, entry, user_input):
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )


async def test_reconfigure_updates_connection(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", title="kostal_piko", data=USER_INPUT
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _reconfigure(
        hass,
        entry,
        {"host": "http://10.0.0.5", "username": "pvserver", "password": "new"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "http://10.0.0.5"
    assert entry.data["password"] == "new"
    assert entry.data["monitored_conditions"] == USER_INPUT["monitored_conditions"]
    # entities are kept
    assert hass.states.get("sensor.kostal_piko_current_power").state == "340"
    assert hass.states.get("sensor.kostal_piko_current_power_2") is None


async def test_reconfigure_rejects_other_inverter(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="OTHER", title="kostal_piko", data=USER_INPUT
    )
    entry.add_to_hass(hass)

    result = await _reconfigure(
        hass,
        entry,
        {"host": "http://10.0.0.5", "username": "pvserver", "password": "pvwr"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data["host"] == USER_INPUT["host"]


async def test_reconfigure_unreachable_shows_error(hass, fake_piko):
    fake_piko.info = None
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", title="kostal_piko", data=USER_INPUT
    )
    entry.add_to_hass(hass)

    result = await _reconfigure(
        hass,
        entry,
        {"host": "http://10.0.0.5", "username": "pvserver", "password": "pvwr"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "could_not_connect"}


async def test_wrong_password_shows_invalid_auth(hass, fake_piko):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CONNECTION, "password": "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_updates_the_password(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123",
        title="kostal_piko",
        data={**USER_INPUT, "password": "wrong"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "pvserver", "password": "right"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "right"
    assert entry.data["host"] == USER_INPUT["host"]


async def test_reauth_with_wrong_password_stays_in_form(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", title="kostal_piko", data=USER_INPUT
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "pvserver", "password": "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_sets_the_update_interval(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SN123", title="kostal_piko", data=USER_INPUT
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.coordinator.update_interval.total_seconds() == 30

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"monitored_conditions": ["current_power"], "scan_interval": 60.0},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 60
    assert isinstance(entry.options["scan_interval"], int)
    # the entry was reloaded with the new interval
    assert entry.runtime_data.coordinator.update_interval.total_seconds() == 60


async def test_unknown_page_layout_shows_unsupported_device(hass, fake_piko):
    fake_piko.parse_fail = True
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device"}
