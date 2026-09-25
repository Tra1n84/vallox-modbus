"""Read-only Vallox setting registers."""

from __future__ import annotations

from modbus_connection.model import Component, boolean, gauge, integer


class ValloxSettings(Component):
    """Configured Vallox profile settings from holding registers."""

    register_space = "holding"
    register_ranges = (
        (20499, 20502),
        (20505, 20508),
        (20511, 20514),
        (20544, 20545),
    )

    away_rh_control_enabled = boolean(20499)
    away_co2_control_enabled = boolean(20500)
    away_fan_speed = integer(20501, signed=False, unit="%")
    away_air_temperature_target = gauge(
        20502,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    home_rh_control_enabled = boolean(20505)
    home_co2_control_enabled = boolean(20506)
    home_fan_speed = integer(20507, signed=False, unit="%")
    home_air_temperature_target = gauge(
        20508,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    boost_rh_control_enabled = boolean(20511)
    boost_co2_control_enabled = boolean(20512)
    boost_fan_speed = integer(20513, signed=False, unit="%")
    boost_air_temperature_target = gauge(
        20514,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    boost_duration = integer(20544, signed=False, unit="min")
    fireplace_duration = integer(20545, signed=False, unit="min")
