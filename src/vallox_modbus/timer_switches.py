"""Vallox timed profile timer switch registers."""

from __future__ import annotations

from modbus_connection.model import Component, boolean

from .validators import boolean_value


class ValloxTimerSwitches(Component):
    """Timer switches of the timed profiles from holding registers.

    While a switch is off, the timer of its profile does not count down. The
    Vallox digital input can also change these registers.
    """

    register_space = "holding"
    register_ranges = (
        (21766, 21767),
        (21772, 21772),
    )

    boost_timer_enabled = boolean(21766, writable=boolean_value)
    fireplace_timer_enabled = boolean(21767, writable=boolean_value)
    extra_timer_enabled = boolean(21772, writable=boolean_value)
