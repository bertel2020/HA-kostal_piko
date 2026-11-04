"""Shared fixtures for the Kostal Piko tests."""
from unittest.mock import patch

import pytest

from custom_components.kostal.client import (
    KostalAuthError,
    KostalConnectionError,
    KostalParseError,
    PikoInfo,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load custom_components in all tests."""
    yield


class FakeData:
    """Stand-in for client.PikoData with the values of a real inverter."""

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
            "status": "Einspeisen (MPP)",
        }
        self.values.update(values)

    def get(self, name):
        return self.values.get(name)


class FakeBAData:
    """Stand-in for client.PikoBAData without BA hardware."""

    def get(self, name):
        return None


class FakeClient:
    """Stand-in for client.KostalClient without network access."""

    info = PikoInfo("SN123", "PIKO 10")  # None: inverter does not answer
    data_values: dict = {}
    fail = False  # simulate an unreachable inverter
    auth_fail = False  # simulate wrong credentials
    ba_fail = False  # simulate a failing BA request only
    parse_fail = False  # simulate pages with an unknown structure
    info_by_host: dict = {}  # several inverters: host -> PikoInfo
    values_by_host: dict = {}  # several inverters: host -> values

    def __init__(self, session, host, username, password):
        self.host = host
        self.username = username
        self.password = password

    def _check(self):
        if FakeClient.auth_fail or (FakeClient.info is not None and self.password == "wrong"):
            raise KostalAuthError("invalid credentials")
        if FakeClient.fail:
            raise KostalConnectionError("no response")

    async def async_get_info(self):
        self._check()
        if FakeClient.info is None:
            raise KostalConnectionError("no response")
        return FakeClient.info_by_host.get(self.host, FakeClient.info)

    async def async_get_data(self):
        self._check()
        if FakeClient.parse_fail:
            raise KostalParseError("Unsupported page layout with 4 values")
        values = {**FakeClient.data_values, **FakeClient.values_by_host.get(self.host, {})}
        return FakeData(**values)

    async def async_get_ba_data(self):
        if FakeClient.ba_fail:
            raise KostalConnectionError("BA failed")
        return FakeBAData()


@pytest.fixture
def fake_piko():
    """Patch the client everywhere it is used."""
    FakeClient.info = PikoInfo("SN123", "PIKO 10")
    FakeClient.data_values = {}
    FakeClient.fail = False
    FakeClient.auth_fail = False
    FakeClient.ba_fail = False
    FakeClient.parse_fail = False
    FakeClient.info_by_host = {}
    FakeClient.values_by_host = {}
    with (
        patch("custom_components.kostal.KostalClient", FakeClient),
        patch("custom_components.kostal.config_flow.KostalClient", FakeClient),
    ):
        yield FakeClient
