"""Read-only Vallox measurement registers."""

from __future__ import annotations

from modbus_connection.model import Component, enum, gauge, integer

from .enums import SensorLevel


class ValloxMeasurements(Component):
    """Current Vallox measurement values from holding registers 4353..4364."""

    register_space = "holding"
    register_ranges = ((4353, 4364),)

    fan_speed = integer(4353, signed=False, unit="%")
    extract_air_temperature = gauge(
        4354,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    exhaust_air_temperature = gauge(
        4355,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    outdoor_air_temperature = gauge(
        4356,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    supply_cell_air_temperature = gauge(
        4357,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    supply_air_temperature = gauge(
        4358,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    rh_level = enum(4359, SensorLevel)
    co2_level = enum(4360, SensorLevel)
    extract_fan_rpm = integer(4361, signed=False, unit="RPM")
    supply_fan_rpm = integer(4362, signed=False, unit="RPM")
    humidity = integer(4363, signed=False, unit="%")
    co2 = integer(4364, signed=False, unit="ppm")
