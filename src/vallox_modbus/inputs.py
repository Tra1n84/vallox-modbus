"""Vallox input state registers."""

from __future__ import annotations

from modbus_connection.model import Component, boolean, integer


class ValloxInputs(Component):
    """Current Vallox input states from holding registers 4365..4370."""

    register_space = "holding"
    register_ranges = ((4365, 4370),)

    fireplace_switch = boolean(4365)
    digital_input = boolean(4366)
    analog_control_input = integer(4367, signed=False, unit="%")
    multisensor_co2_raw = integer(4368, signed=False)
    multisensor_temperature_raw = integer(4369, signed=False)
    multisensor_humidity_raw = integer(4370, signed=False)
