"""Vallox setting registers."""

from __future__ import annotations

from datetime import date

from modbus_connection.model import Component, boolean, gauge, integer

from .validators import air_temperature_target, duration_minutes, percent


class ValloxSettings(Component):
    """Configured Vallox profile settings from holding registers."""

    register_space = "holding"
    register_ranges = (
        (20499, 20502),
        (20505, 20508),
        (20511, 20514),
        (20544, 20548),
    )

    away_rh_control_enabled = boolean(20499)
    away_co2_control_enabled = boolean(20500)
    away_fan_speed = integer(20501, signed=False, writable=percent, unit="%")
    away_air_temperature_target = gauge(
        20502,
        0.01,
        offset=-273.15,
        signed=False,
        writable=air_temperature_target,
        unit="°C",
    )
    home_rh_control_enabled = boolean(20505)
    home_co2_control_enabled = boolean(20506)
    home_fan_speed = integer(20507, signed=False, writable=percent, unit="%")
    home_air_temperature_target = gauge(
        20508,
        0.01,
        offset=-273.15,
        signed=False,
        writable=air_temperature_target,
        unit="°C",
    )
    boost_rh_control_enabled = boolean(20511)
    boost_co2_control_enabled = boolean(20512)
    boost_fan_speed = integer(20513, signed=False, writable=percent, unit="%")
    boost_air_temperature_target = gauge(
        20514,
        0.01,
        offset=-273.15,
        signed=False,
        writable=air_temperature_target,
        unit="°C",
    )
    boost_duration = integer(20544, signed=False, writable=duration_minutes, unit="min")
    fireplace_duration = integer(
        20545,
        signed=False,
        writable=duration_minutes,
        force_fc16=True,
        unit="min",
    )
    filter_changed_day = integer(20546, signed=False)
    filter_changed_month = integer(20547, signed=False)
    filter_changed_year = integer(20548, signed=False)

    @property
    def filter_change_date(self) -> date | None:
        """Last filter change date.

        The year register holds two digits (0..99) and is read as 2000 + YY.
        Returns None if a value is missing or the stored date is invalid.
        """

        day = self.filter_changed_day
        month = self.filter_changed_month
        year = self.filter_changed_year
        if day is None or month is None or year is None:
            return None
        if not 0 <= year <= 99:
            return None
        try:
            return date(2000 + year, month, day)
        except ValueError:
            return None
