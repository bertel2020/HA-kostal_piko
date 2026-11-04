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
