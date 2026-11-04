"""Tests for the diagnostics download."""
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kostal.const import DOMAIN
from custom_components.kostal.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_secrets(hass, fake_piko):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="kostal_piko",
        unique_id="SN123",
        data={
            "host": "http://192.168.1.50",
            "username": "pvserver",
            "password": "secret-pw",
            "monitored_conditions": ["current_power", "dc_power"],
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    text = str(result)
    for secret in ("192.168.1.50", "pvserver", "secret-pw", "SN123"):
        assert secret not in text
    assert result["entry"]["data"]["host"] == "**REDACTED**"
    assert result["inverter"]["model"] == "PIKO 10"
    assert result["values"]["current_power"] == 340
    assert result["values"]["dc_power"] == 343
    assert result["coordinator"]["last_update_success"] is True
