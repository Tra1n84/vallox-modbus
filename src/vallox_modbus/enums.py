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


class ModbusParity(IntEnum):
    """Vallox Modbus parity code from register 20484."""

    NONE = 0
    EVEN = 1
    ODD = 2


class HeatRecoveryCellType(IntEnum):
    """Vallox heat recovery cell type from register 20538."""

    ALUMINIUM = 0
    PLASTIC = 1
    ENTHALPY = 2


class HeaterType(IntEnum):
    """Vallox heater type from registers 20539 and 20540."""

    NONE = 0
    ELECTRIC = 1
    WATER = 2
