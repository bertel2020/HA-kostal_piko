"""Calculated values derived from the inverter data."""

from __future__ import annotations


def string_power(data, string: int) -> int | None:
    """Return the power of one string in W (voltage * current), or None."""
    voltage = data.get(f"string{string}_voltage")
    current = data.get(f"string{string}_current")
    if voltage is None or current is None:
        return None
    return round(voltage * current)


def dc_power(data) -> int | None:
    """Return the DC input power in W: sum of the power of all strings.

    Returns None if the inverter reports no string values at all.
    """
    powers = [string_power(data, string) for string in (1, 2, 3)]
    powers = [power for power in powers if power is not None]
    return sum(powers) if powers else None


def windowed_efficiency(samples) -> float | None:
    """Return the efficiency in percent over several (AC, DC) power samples.

    The sum of the AC powers is divided by the sum of the DC powers, so a
    sample with a high power counts more than one with a low power. A single
    snapshot is imprecise: the currents are rounded to 0.01 A and the AC and
    DC values are not measured at exactly the same moment.
    """
    ac = sum(sample[0] for sample in samples)
    dc = sum(sample[1] for sample in samples)
    if dc <= 0:
        return None
    return round(ac / dc * 100, 1)


def mean_power(samples) -> int | None:
    """Return the mean of several AC power samples in W, or None without samples."""
    if not samples:
        return None
    return round(sum(samples) / len(samples))


_DATA_SENSORS = (
    "current_power", "total_energy", "daily_energy",
    "string1_voltage", "string1_current", "string2_voltage", "string2_current",
    "string3_voltage", "string3_current",
    "l1_voltage", "l1_power", "l2_voltage", "l2_power", "l3_voltage", "l3_power",
    "status",
)  # fmt: skip
_BA_SENSORS = (
    "solar_generator_power", "consumption_phase_1", "consumption_phase_2", "consumption_phase_3",
)  # fmt: skip


def available_sensors(data, ba_data) -> set[str]:
    """Return the sensors this inverter can provide.

    The BA (own consumption) sensors only count as available when the BA page
    reports a value other than 0, because without BA hardware it shows zeros.
    """
    found = {name for name in _DATA_SENSORS if data.get(name) is not None}
    powers = [string for string in (1, 2, 3) if string_power(data, string) is not None]
    found.update(f"string{string}_power" for string in powers)
    if powers:
        found.add("dc_power")
        if "current_power" in found:
            found.add("efficiency")
    if "current_power" in found:
        found.add("average_power_15min")
    if ba_data is not None:
        values = {name: ba_data.get(name) for name in _BA_SENSORS}
        if any(value for value in values.values()):
            found.update(name for name, value in values.items() if value is not None)
    return found
