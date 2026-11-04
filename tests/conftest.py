"""Shared fixtures for the Kostal Piko tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load custom_components in all tests."""
    yield


class FakeData:
    """Stand-in for kostalpiko.PikoData with the values of a real inverter."""

    def __init__(self, **values):
        self.values = {
            "current_power": 340,
            "total_energy": 125133,
            "daily_energy": 0.3,
            "string1_voltage": 549,
            "string1_current": 0.18,
            "string2_voltage": 626,
            "string2_current": 0.2,
            "string3_voltage": 663,
            "string3_current": 0.18,
            "l1_voltage": 234,
            "l1_power": 0,
            "piko_status": "Einspeisen (MPP)",
        }
        self.values.update(values)

    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda: self.values.get(name[4:])
        raise AttributeError(name)


class FakePikoBAData:
    """Stand-in for PikoBAData without BA hardware."""

    def get_solar_generator_power(self):
        return "No BA sensor installed"


class FakePiko:
    """Stand-in for kostalpiko.Piko without network access."""

    info = ["SN123", "PIKO 10"]
    data_values: dict = {}
    fail = False  # simulate an unreachable inverter
    ba_fail = False  # simulate a failing BA request only

    def __init__(self, host=None, username="pvserver", password="pvwr"):
        self.host = host

    def _get_info(self):
        return FakePiko.info

    def _get_raw_content(self):
        # like the real library: None on connection errors and timeouts
        return None if FakePiko.fail else ["raw"]

    def _get_content_of_own_consumption(self):
        if FakePiko.ba_fail:
            raise ConnectionError("BA failed")
        return []


@pytest.fixture
def fake_piko():
    """Patch the Piko client everywhere it is used."""
    FakePiko.info = ["SN123", "PIKO 10"]
    FakePiko.data_values = {}
    FakePiko.fail = False
    FakePiko.ba_fail = False
    with (
        patch("custom_components.kostal.Piko", FakePiko),
        patch("custom_components.kostal.config_flow.Piko", FakePiko),
        patch(
            "custom_components.kostal.coordinator.PikoData",
            lambda raw: FakeData(**FakePiko.data_values),
        ),
        patch(
            "custom_components.kostal.coordinator.PikoBAData",
            lambda raw: FakePikoBAData(),
        ),
    ):
        yield FakePiko
