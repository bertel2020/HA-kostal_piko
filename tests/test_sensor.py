"""Tests for setup, entities and entity preservation."""
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kostal.const import DOMAIN

CONDITIONS = [
    "current_power",
    "total_energy",
    "status",
    "string1_power",
    "dc_power",
    "efficiency",
    "solar_generator_power",
]


def _entry(**extra):
    return MockConfigEntry(
        domain=DOMAIN,
        title="kostal_piko",
        data={
            "host": "http://192.168.1.50",
            "username": "pvserver",
            "password": "pvwr",
            "monitored_conditions": CONDITIONS,
        },
        **extra,
    )


async def test_sensors_are_created(hass, fake_piko):
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.kostal_piko_current_power").state == "340"
    assert hass.states.get("sensor.kostal_piko_total_energy").state == "125133"
    assert hass.states.get("sensor.kostal_piko_status").state == "Einspeisen (MPP)"
    assert hass.states.get("sensor.kostal_piko_string_1_power").state == "99"
    assert hass.states.get("sensor.kostal_piko_dc_power").state == "343"
    assert hass.states.get("sensor.kostal_piko_efficiency").state == "99.1"
    # no BA hardware: the library text must not end up as a numeric state
    assert hass.states.get("sensor.kostal_piko_solar_generator_power").state == "unknown"


async def test_entity_attributes(hass, fake_piko):
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    energy = hass.states.get("sensor.kostal_piko_total_energy")
    assert energy.attributes["device_class"] == "energy"
    assert energy.attributes["state_class"] == "total_increasing"
    assert energy.attributes["unit_of_measurement"] == "kWh"
    efficiency = hass.states.get("sensor.kostal_piko_efficiency")
    assert efficiency.attributes["unit_of_measurement"] == "%"


async def test_existing_entities_are_kept(hass, fake_piko):
    """An entity registered by an older version keeps its entity_id."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN123 Current power",  # unique_id format of all previous versions
        suggested_object_id="kostal_piko_current_power",
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "SN123 Current power")
    assert entity_id == "sensor.kostal_piko_current_power"
    assert hass.states.get(entity_id).state == "340"


async def test_unique_id_and_device(hass, fake_piko):
    entry = _entry()  # created by an older version: no unique_id
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "SN123"
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "SN123"), entry.entry_id
    )
    assert device.manufacturer == "Kostal"
    assert device.model == "PIKO 10"


async def test_unreachable_inverter_is_retried(hass, fake_piko):
    fake_piko.info = None
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_and_reload(hass, fake_piko):
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.kostal_piko_current_power").state == "340"
    # reloading must not create duplicates
    assert hass.states.get("sensor.kostal_piko_current_power_2") is None


async def _setup(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_outage_makes_entities_unavailable_after_three_failures(
    hass, fake_piko, caplog
):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator
    entity = "sensor.kostal_piko_current_power"
    assert hass.states.get(entity).state == "340"

    fake_piko.fail = True
    for _ in range(2):  # one or two missed polls keep the last value
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity).state == "340"

    await coordinator.async_refresh()  # third failure in a row
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "unavailable"
    assert hass.states.get("sensor.kostal_piko_efficiency").state == "unavailable"
    assert caplog.text.count("Error fetching kostal data") == 1

    await coordinator.async_refresh()  # further failures are not logged again
    assert caplog.text.count("Error fetching kostal data") == 1

    fake_piko.fail = False
    fake_piko.data_values = {"current_power": 400}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "400"
    assert "Fetching kostal data recovered" in caplog.text


async def test_single_failure_resets_the_counter(hass, fake_piko):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator
    entity = "sensor.kostal_piko_current_power"

    for _ in range(5):  # failures that are never three in a row
        fake_piko.fail = True
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        fake_piko.fail = False
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "340"


async def test_ba_failure_does_not_affect_inverter_values(hass, fake_piko):
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator

    fake_piko.ba_fail = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.kostal_piko_current_power").state == "340"


async def test_unreachable_inverter_at_first_poll_is_retried(hass, fake_piko):
    fake_piko.fail = True  # info is readable, but the data page is not
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


def _reauth_flows(hass):
    return [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_wrong_password_at_setup_starts_reauth(hass, fake_piko):
    fake_piko.auth_fail = True
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(_reauth_flows(hass)) == 1


async def test_password_change_during_operation_starts_reauth(hass, fake_piko):
    entry = await _setup(hass)
    assert not _reauth_flows(hass)

    fake_piko.auth_fail = True  # password was changed on the inverter
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(_reauth_flows(hass)) == 1


async def test_efficiency_is_averaged_over_five_minutes(hass, fake_piko, freezer):
    from datetime import timedelta

    entry = await _setup(hass)  # 340 W AC / 343 W DC
    coordinator = entry.runtime_data.coordinator
    entity = "sensor.kostal_piko_efficiency"
    assert hass.states.get(entity).state == "99.1"

    # second poll: 540 W AC / 602 W DC (strings 0.33/0.34/0.31 A)
    freezer.tick(timedelta(seconds=30))
    fake_piko.data_values = {
        "current_power": 540,
        "string1_voltage": 531, "string1_current": 0.33,
        "string2_voltage": 650, "string2_current": 0.34,
        "string3_voltage": 665, "string3_current": 0.31,
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # (340 + 540) / (343 + 602) = 93.1 %, not the single value 89.7 %
    assert hass.states.get(entity).state == "93.1"

    # after more than five minutes the first sample is dropped
    freezer.tick(timedelta(minutes=5, seconds=1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "89.7"  # only 540 / 602 remain


async def test_efficiency_unknown_in_standby_after_the_window(hass, fake_piko, freezer):
    from datetime import timedelta

    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator
    entity = "sensor.kostal_piko_efficiency"

    fake_piko.data_values = {
        "current_power": 0,
        "string1_voltage": 0, "string1_current": 0.0,
        "string2_voltage": 0, "string2_current": 0.0,
        "string3_voltage": 0, "string3_current": 0.0,
    }
    freezer.tick(timedelta(seconds=30))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "99.1"  # old sample still in window

    freezer.tick(timedelta(minutes=5, seconds=1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "unknown"


@pytest.mark.parametrize(
    ("interval", "failures_until_unavailable"),
    [(10, 9), (30, 3), (90, 1), (600, 1)],
)
async def test_unavailable_after_about_90_seconds_for_any_interval(
    hass, fake_piko, interval, failures_until_unavailable
):
    entry = _entry(options={"scan_interval": interval})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    assert coordinator.update_interval.total_seconds() == interval
    entity = "sensor.kostal_piko_current_power"

    fake_piko.fail = True
    for _ in range(failures_until_unavailable - 1):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity).state == "340"

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity).state == "unavailable"


async def test_two_inverters_keep_their_own_entities(hass, fake_piko):
    """Regression for the upstream bug where a second inverter got mixed up."""
    from custom_components.kostal.client import PikoInfo

    fake_piko.info_by_host = {
        "http://10.0.0.1": PikoInfo("SN-A", "PIKO 10.1"),
        "http://10.0.0.2": PikoInfo("SN-B", "PIKO 5.5"),
    }
    fake_piko.values_by_host = {
        "http://10.0.0.1": {"current_power": 340},
        "http://10.0.0.2": {"current_power": 1200},
    }
    entries = []
    for title, host in (("piko_a", "http://10.0.0.1"), ("piko_b", "http://10.0.0.2")):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title,
            data={
                "host": host,
                "username": "pvserver",
                "password": "pvwr",
                "monitored_conditions": ["current_power"],
            },
        )
        entry.add_to_hass(hass)
        entries.append(entry)
    # Home Assistant sets up all entries of the integration together
    await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()
    assert [entry.state for entry in entries] == [ConfigEntryState.LOADED] * 2

    assert hass.states.get("sensor.piko_a_current_power").state == "340"
    assert hass.states.get("sensor.piko_b_current_power").state == "1200"

    registry = er.async_get(hass)
    for entry, serial in zip(entries, ("SN-A", "SN-B"), strict=True):
        entity = registry.async_get_entity_id("sensor", DOMAIN, f"{serial} Current power")
        assert registry.async_get(entity).config_entry_id == entry.entry_id
    device_registry = dr.async_get(hass)
    for entry in entries:
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        assert len(devices) == 1
