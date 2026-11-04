"""Tests for the calculated sensor values."""
from custom_components.kostal.sensor import _dc_power, _efficiency, _string_power

from .conftest import FakeData


def test_string_power_matches_inverter_values():
    data = FakeData()
    assert [_string_power(data, n) for n in (1, 2, 3)] == [99, 125, 119]


def test_dc_power_is_sum_of_strings():
    assert _dc_power(FakeData()) == 343


def test_missing_string_is_unknown():
    data = FakeData(string3_voltage=None, string3_current=None)
    assert _string_power(data, 3) is None
    assert _dc_power(data) == 224


def test_no_string_data_gives_unknown_dc_power():
    data = FakeData(
        string1_voltage=None, string1_current=None,
        string2_voltage=None, string2_current=None,
        string3_voltage=None, string3_current=None,
    )
    assert _dc_power(data) is None
    assert _efficiency(data) is None


def test_efficiency():
    assert _efficiency(FakeData()) == 99.1


def test_efficiency_is_unknown_without_dc_input():
    data = FakeData(
        current_power=0,
        string1_voltage=0, string1_current=0.0,
        string2_voltage=0, string2_current=0.0,
        string3_voltage=0, string3_current=0.0,
    )
    assert _dc_power(data) == 0
    assert _efficiency(data) is None
