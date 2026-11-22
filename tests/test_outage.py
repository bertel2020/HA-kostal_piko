"""Tests for the outage detection: problem binary sensor and repair issue."""
from datetime import timedelta

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kostal.const import DOMAIN, OUTAGE_AFTER

PROBLEM = "binary_sensor.kostal_piko_problem"


async def _setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="kostal_piko",
        data={
            "host": "http://192.168.1.50",
            "username": "pvserver",
            "password": "pvwr",
            "monitored_conditions": ["current_power"],
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _issue(hass, entry):
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"inverter_unreachable_{entry.entry_id}"
    )


async def test_no_problem_while_the_inverter_answers(hass, fake_piko):
    entry = await _setup(hass)
    assert hass.states.get(PROBLEM).state == "off"
    assert _issue(hass, entry) is None


async def test_short_dropout_raises_no_issue(hass, fake_piko, freezer):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator

    fake_piko.fail = True
    await coordinator.async_refresh()
    freezer.tick(OUTAGE_AFTER - timedelta(minutes=1))
    await coordinator.async_refresh()
    await coordinator.async_refresh()  # third failure: sensors become unavailable
    await hass.async_block_till_done()

    # sensors are unavailable by now, but it is not yet an outage
    assert hass.states.get("sensor.kostal_piko_current_power").state == "unavailable"
    assert hass.states.get(PROBLEM).state == "off"
    assert _issue(hass, entry) is None


async def test_outage_raises_issue_and_recovery_removes_it(hass, fake_piko, freezer):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator

    fake_piko.fail = True
    await coordinator.async_refresh()
    freezer.tick(OUTAGE_AFTER + timedelta(seconds=1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # the problem sensor stays available while everything else is not
    assert hass.states.get(PROBLEM).state == "on"
    issue = _issue(hass, entry)
    assert issue is not None
    assert issue.translation_key == "inverter_unreachable"
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue.is_fixable

    fake_piko.fail = False
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(PROBLEM).state == "off"
    assert _issue(hass, entry) is None


async def test_unloading_removes_the_issue(hass, fake_piko, freezer):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator

    fake_piko.fail = True
    await coordinator.async_refresh()
    freezer.tick(OUTAGE_AFTER + timedelta(seconds=1))
    await coordinator.async_refresh()
    assert _issue(hass, entry) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert _issue(hass, entry) is None
