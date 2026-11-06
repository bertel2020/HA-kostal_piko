"""Tests for the calculated sensor values."""
from custom_components.kostal.calculations import (
    dc_power,
    string_power,
    mean_power,
    specific_yield,
    utilization,
    windowed_efficiency,
)

from .conftest import FakeData


def test_string_power_matches_inverter_values():
    data = FakeData()
    assert [string_power(data, n) for n in (1, 2, 3)] == [99, 125, 119]


def test_dc_power_is_sum_of_strings():
    assert dc_power(FakeData()) == 343


def test_missing_string_is_unknown():
    data = FakeData(string3_voltage=None, string3_current=None)
    assert string_power(data, 3) is None
    assert dc_power(data) == 224


def test_no_string_data_gives_unknown_dc_power():
    data = FakeData(
        string1_voltage=None, string1_current=None,
        string2_voltage=None, string2_current=None,
        string3_voltage=None, string3_current=None,
    )
    assert dc_power(data) is None


def test_windowed_efficiency_is_power_weighted():
    # Plain average of the two quotients would be 94.5 %, but the sample with
    # 1000 W counts ten times as much as the one with 100 W.
    samples = [(900, 1000), (99, 100)]
    assert windowed_efficiency(samples) == 90.8  # (900+99) / (1000+100)


def test_windowed_efficiency_without_dc_is_zero():
    assert windowed_efficiency([]) == 0
    assert windowed_efficiency([(0, 0)]) == 0


def test_mean_power_is_rounded():
    assert mean_power([100, 201]) == 150  # 150.5 rounds to the even value
    assert mean_power([0, 0]) == 0


def test_mean_power_without_samples_is_unknown():
    assert mean_power([]) is None


def test_utilization_is_ac_power_in_percent_of_the_maximum():
    assert utilization(3500, 7000) == 50.0
    assert utilization(0, 7000) == 0.0
    assert utilization(3500, 0) is None
    assert utilization(None, 7000) is None


def test_specific_yield_ignores_unused_strings():
    # string 3 unused (0): 12 kWh on 5 + 3 kWp
    assert specific_yield(12, [5000, 3000, 0]) == 1.5
    assert specific_yield(12, [0, 0, 0]) is None
    assert specific_yield(None, [5000]) is None
