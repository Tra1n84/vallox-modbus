"""Write validators for documented Vallox register ranges."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from .enums import BasicProfile, SystemMode

MIN_AIR_TEMPERATURE_TARGET = 5.0
MAX_AIR_TEMPERATURE_TARGET = 25.0
MIN_DURATION = 1
MAX_DURATION = 65535
MIN_TIMER = 0
MAX_TIMER = 65535
MIN_PERCENT = 0
MAX_PERCENT = 100


def percent(value: Any) -> int:
    """Validate a percent value."""

    return integer_range(value, MIN_PERCENT, MAX_PERCENT)


def timer_minutes(value: Any) -> int:
    """Validate a current timer value in minutes."""

    return integer_range(value, MIN_TIMER, MAX_TIMER)


def duration_minutes(value: Any) -> int:
    """Validate a configured duration value in minutes."""

    return integer_range(value, MIN_DURATION, MAX_DURATION)


def air_temperature_target(value: Any) -> float:
    """Validate a supply air temperature target in Celsius."""

    if isinstance(value, bool):
        raise ValueError("temperature target must be a number")
    result = float(value)
    if MIN_AIR_TEMPERATURE_TARGET <= result <= MAX_AIR_TEMPERATURE_TARGET:
        return result
    raise ValueError(
        "temperature target must be between "
        f"{MIN_AIR_TEMPERATURE_TARGET} and {MAX_AIR_TEMPERATURE_TARGET} °C"
    )


def boolean_value(value: Any) -> bool:
    """Validate a boolean value."""

    if isinstance(value, bool):
        return value
    raise ValueError("value must be a boolean")


def basic_profile(value: Any) -> BasicProfile:
    """Validate a writable basic profile."""

    return enum_value(value, BasicProfile)


def system_mode(value: Any) -> SystemMode:
    """Validate a writable system mode."""

    result = enum_value(value, SystemMode)
    if result in {SystemMode.NORMAL, SystemMode.OFF}:
        return result
    raise ValueError(f"unsupported system mode {result!r}")


def integer_range(value: Any, minimum: int, maximum: int) -> int:
    """Validate an integer range."""

    if isinstance(value, bool):
        raise ValueError("value must be an integer")
    result = int(value)
    if result != value:
        raise ValueError("value must be an integer")
    if minimum <= result <= maximum:
        return result
    raise ValueError(f"value must be between {minimum} and {maximum}")


def enum_value[E: IntEnum](value: Any, enum_type: type[E]) -> E:
    """Validate an IntEnum value."""

    if isinstance(value, enum_type):
        return value
    if isinstance(value, bool):
        raise ValueError(f"value must be a {enum_type.__name__}")
    try:
        return enum_type(value)
    except ValueError as err:
        raise ValueError(f"value must be a {enum_type.__name__}") from err
