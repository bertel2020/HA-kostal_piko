"""Tests for setup, entities and entity preservation."""
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
