"""Documented Vallox Modbus enumerations."""

from enum import IntEnum


class BasicProfile(IntEnum):
    """Vallox basic profile from register 4609."""

    HOME = 0
    AWAY = 1


class HeatExchangerState(IntEnum):
    """Vallox heat exchanger cell state from register 4616."""

    HEAT_RECOVERY = 0
    COOL_RECOVERY = 1
    BYPASS = 2
    DEFROSTING = 3


class SensorLevel(IntEnum):
    """Vallox sensor level for RH and CO2 level registers."""

    NO_SENSOR = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SystemMode(IntEnum):
    """Documented Vallox override system modes from register 4610."""

    NORMAL = 0
    OFF = 5
