"""Constants for the Kostal piko integration."""
from datetime import timedelta

from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    )

DOMAIN = "kostal"

DEFAULT_NAME = "Kostal Piko"

# Polling interval of the inverter in seconds (adjustable in the options).
# The inverter needs about 1 s per page, so shorter than 10 s makes no sense.
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# The efficiency is averaged over this period (power-weighted).
EFFICIENCY_WINDOW = timedelta(minutes=5)

# The average power is the mean of the polled AC power over this period.
POWER_AVERAGE_WINDOW = timedelta(minutes=15)

# Entities keep their last value for this long after the first failed poll
# before they become unavailable (with the default interval: 3 polls).
UNAVAILABLE_AFTER = timedelta(seconds=90)


SENSOR_TYPES = {
    "solar_generator_power": ["Solar generator power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    "consumption_phase_1": ["Consumption phase 1", UnitOfPower.WATT, "mdi:power-socket-eu", "measurement", "power"],
    "consumption_phase_2": ["Consumption phase 2", UnitOfPower.WATT, "mdi:power-socket-eu", "measurement", "power"],
    "consumption_phase_3": ["Consumption phase 3", UnitOfPower.WATT, "mdi:power-socket-eu", "measurement", "power"],
    "current_power": ["Current power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    "total_energy": ["Total energy", UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-power", "total_increasing", "energy"],
    "daily_energy": ["Daily energy", UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-power", "total_increasing", "energy"],
    "string1_voltage": ["String 1 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "string1_current": ["String 1 current", UnitOfElectricCurrent.AMPERE, "mdi:flash", "measurement", "current"],
    "string2_voltage": ["String 2 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "string2_current": ["String 2 current", UnitOfElectricCurrent.AMPERE, "mdi:flash", "measurement", "current"],
    "string3_voltage": ["String 3 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "string3_current": ["String 3 current", UnitOfElectricCurrent.AMPERE, "mdi:flash", "measurement", "current"],
    "l1_voltage": ["L1 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "l1_power": ["L1 power", UnitOfPower.WATT, "mdi:power-plug", "measurement", "power"],
    "l2_voltage": ["L2 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "l2_power": ["L2 power", UnitOfPower.WATT, "mdi:power-plug", "measurement", "power"],
    "l3_voltage": ["L3 voltage",  UnitOfElectricPotential.VOLT, "mdi:current-ac", "measurement", "voltage"],
    "l3_power": ["L3 power", UnitOfPower.WATT, "mdi:power-plug", "measurement", "power"],
    "status": ["Status", None, "mdi:solar-power", None, None],
    # Calculated sensors
    "string1_power": ["String 1 power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    "string2_power": ["String 2 power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    "string3_power": ["String 3 power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    "dc_power": ["DC power", UnitOfPower.WATT, "mdi:solar-power", "measurement", "power"],
    # AC output power / DC input power (sum of string V * I)
    "efficiency": ["Efficiency", PERCENTAGE, "mdi:percent", "measurement", None],
    # Mean of the AC power over the last POWER_AVERAGE_WINDOW
    "average_power_15min": ["Average power 15 min", UnitOfPower.WATT, "mdi:chart-line", "measurement", "power"],
}

ISSUES_URL = "https://github.com/bertel2020/HA-kostal_piko/issues"
