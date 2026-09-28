"""Vallox optional sensor registers."""

from __future__ import annotations

from modbus_connection.model import Component, gauge, integer

NO_SENSOR = 65535


class ValloxSensors(Component):
    """Optional Vallox sensor values from documented holding registers."""

    register_space = "holding"
    register_ranges = (
        (4372, 4384),
        (4389, 4394),
    )

    internal_humidity_sensor_raw = integer(4372, signed=False, nan=NO_SENSOR)
    rh_sensor_0 = integer(4373, signed=False, nan=NO_SENSOR, unit="%")
    rh_sensor_1 = integer(4374, signed=False, nan=NO_SENSOR, unit="%")
    rh_sensor_2 = integer(4375, signed=False, nan=NO_SENSOR, unit="%")
    rh_sensor_3 = integer(4376, signed=False, nan=NO_SENSOR, unit="%")
    rh_sensor_4 = integer(4377, signed=False, nan=NO_SENSOR, unit="%")
    rh_sensor_5 = integer(4378, signed=False, nan=NO_SENSOR, unit="%")
    co2_sensor_0 = integer(4379, signed=False, nan=NO_SENSOR, unit="ppm")
    co2_sensor_1 = integer(4380, signed=False, nan=NO_SENSOR, unit="ppm")
    co2_sensor_2 = integer(4381, signed=False, nan=NO_SENSOR, unit="ppm")
    co2_sensor_3 = integer(4382, signed=False, nan=NO_SENSOR, unit="ppm")
    co2_sensor_4 = integer(4383, signed=False, nan=NO_SENSOR, unit="ppm")
    co2_sensor_5 = integer(4384, signed=False, nan=NO_SENSOR, unit="ppm")
    optional_temperature = gauge(
        4389,
        0.01,
        offset=-273.15,
        signed=False,
        unit="°C",
    )
    voc_level = integer(4390, signed=False, unit="ppm")
    voc_sensor_0 = integer(4391, signed=False, nan=NO_SENSOR, unit="ppm")
    voc_sensor_1 = integer(4392, signed=False, nan=NO_SENSOR, unit="ppm")
    voc_sensor_2 = integer(4393, signed=False, nan=NO_SENSOR, unit="ppm")
    voc_sensor_3 = integer(4394, signed=False, nan=NO_SENSOR, unit="ppm")

    @property
    def internal_humidity_sensor(self) -> float | None:
        """Internal humidity sensor value in percent."""

        if self.internal_humidity_sensor_raw is None:
            return None
        value = (self.internal_humidity_sensor_raw * 100 - 62039) / 2604
        if 0 <= value <= 100:
            return value
        return None

    @property
    def rh_sensors(self) -> tuple[int | None, ...]:
        """Humidity sensors 0..5."""

        return (
            self.rh_sensor_0,
            self.rh_sensor_1,
            self.rh_sensor_2,
            self.rh_sensor_3,
            self.rh_sensor_4,
            self.rh_sensor_5,
        )

    @property
    def co2_sensors(self) -> tuple[int | None, ...]:
        """CO2 sensors 0..5."""

        return (
            self.co2_sensor_0,
            self.co2_sensor_1,
            self.co2_sensor_2,
            self.co2_sensor_3,
            self.co2_sensor_4,
            self.co2_sensor_5,
        )

    @property
    def voc_sensors(self) -> tuple[int | None, ...]:
        """VOC sensors 0..3."""

        return (
            self.voc_sensor_0,
            self.voc_sensor_1,
            self.voc_sensor_2,
            self.voc_sensor_3,
        )
