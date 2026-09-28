"""Vallox runtime state registers."""

from __future__ import annotations

from modbus_connection.model import Component, boolean, enum, integer

from .enums import BasicProfile, HeatExchangerState, SystemMode
from .validators import basic_profile, system_mode, timer_minutes


class ValloxRuntime(Component):
    """Current Vallox runtime state from holding registers 4609..4621."""

    register_space = "holding"
    register_ranges = ((4609, 4621),)

    basic_profile = enum(4609, BasicProfile, writable=basic_profile)
    system_mode = enum(4610, SystemMode, writable=system_mode)
    defrosting = boolean(4611)
    boost_timer = integer(4612, signed=False, writable=timer_minutes, unit="min")
    fireplace_timer = integer(4613, signed=False, writable=timer_minutes, unit="min")
    extra_timer = integer(4614, signed=False, writable=timer_minutes, unit="min")
    weekly_timer_enabled = boolean(4615)
    heat_exchanger_state = enum(4616, HeatExchangerState)
    total_uptime_years = integer(4617, signed=False, unit="a")
    total_uptime_hours = integer(4618, signed=False, unit="h")
    current_uptime_hours = integer(4619, signed=False, unit="h")
    filter_remaining = integer(4620, signed=False, unit="days")
    fault = boolean(4621)
