"""Top-level Vallox Modbus device object."""

from __future__ import annotations

from typing import Final

from modbus_connection import ModbusError, ModbusUnit
from modbus_connection.model import Device, UpdateReport

from .configuration import ValloxConfiguration
from .enums import BasicProfile, SystemMode
from .exceptions import ValloxConnectionError, ValloxError
from .inputs import ValloxInputs
from .measurements import ValloxMeasurements
from .runtime import ValloxRuntime
from .sensors import ValloxSensors
from .settings import ValloxSettings

VALLOX_TIMEOUT: Final = 5.0
VALLOX_CONNECT_DELAY: Final = 0.5
VALLOX_MESSAGE_SPACING: Final = 0.15


class ValloxDevice(Device):
    """Vallox MV device model."""

    configuration: ValloxConfiguration
    inputs: ValloxInputs
    measurements: ValloxMeasurements
    runtime: ValloxRuntime
    sensors: ValloxSensors
    settings: ValloxSettings

    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        unit.require_timeout(VALLOX_TIMEOUT)
        unit.require_connect_delay(VALLOX_CONNECT_DELAY)
        unit.set_message_spacing(VALLOX_MESSAGE_SPACING)
        self.configuration = ValloxConfiguration(unit)
        self.inputs = ValloxInputs(unit)
        self.measurements = ValloxMeasurements(unit)
        self.runtime = ValloxRuntime(unit)
        self.sensors = ValloxSensors(unit)
        self.settings = ValloxSettings(unit)

    @classmethod
    async def async_probe(cls, unit: ModbusUnit) -> ValloxDevice:
        """Validate that a Modbus unit plausibly serves Vallox MV registers."""

        device = cls(unit)
        try:
            report = await device.async_poll(("measurements", "runtime"))
        except ModbusError as err:
            raise ValloxConnectionError(str(err)) from err

        if not report.complete:
            error = next(iter(report.failed.values()))
            raise ValloxConnectionError(str(error)) from error

        device._validate_probe_values()
        return device

    def _validate_probe_values(self) -> None:
        """Check a small set of live values for conservative plausibility."""

        fan_speed = self.measurements.fan_speed
        if fan_speed is None or not 0 <= fan_speed <= 100:
            msg = f"fan speed is not plausible: {fan_speed!r}"
            raise ValloxError(msg)

        temperatures = (
            self.measurements.extract_air_temperature,
            self.measurements.exhaust_air_temperature,
            self.measurements.outdoor_air_temperature,
            self.measurements.supply_cell_air_temperature,
            self.measurements.supply_air_temperature,
        )
        for temperature in temperatures:
            if temperature is None or not -50.0 <= temperature <= 100.0:
                msg = f"temperature is not plausible: {temperature!r}"
                raise ValloxError(msg)

        if self.runtime.basic_profile is None:
            msg = "basic profile is not plausible"
            raise ValloxError(msg)

        if self.runtime.system_mode is None:
            msg = "system mode is not plausible"
            raise ValloxError(msg)

    async def async_update_readings(self) -> UpdateReport:
        """Update frequently changing measurement and runtime readings."""

        return await self.async_poll(("measurements", "runtime", "inputs", "sensors"))

    async def async_update_settings(
        self, report: UpdateReport | None = None
    ) -> UpdateReport:
        """Update configured profile settings."""

        return await self.async_poll(("settings", "configuration"), report)

    async def async_update(self) -> UpdateReport:
        """Update readings and settings in one report."""

        report = await self.async_update_readings()
        return await self.async_update_settings(report)

    async def async_set_power(self, on: bool) -> None:
        """Set normal operation on or off."""

        await self.runtime.write(
            "system_mode",
            SystemMode.NORMAL if on else SystemMode.OFF,
        )

    async def async_set_basic_profile(self, profile: BasicProfile) -> None:
        """Set the basic Home/Away/Automatic profile."""

        await self.runtime.write("basic_profile", profile)

    async def async_set_boost_timer(self, minutes: int) -> None:
        """Set the current Boost timer in minutes."""

        await self.runtime.write("boost_timer", minutes)

    async def async_set_fireplace_timer(self, minutes: int) -> None:
        """Set the current Fireplace timer in minutes."""

        await self.runtime.write("fireplace_timer", minutes)

    async def async_set_extra_timer(self, minutes: int) -> None:
        """Set the current Extra timer in minutes."""

        await self.runtime.write("extra_timer", minutes)

    async def async_set_away_fan_speed(self, percent: int) -> None:
        """Set the configured Away fan speed."""

        await self.settings.write("away_fan_speed", percent)

    async def async_set_home_fan_speed(self, percent: int) -> None:
        """Set the configured Home fan speed."""

        await self.settings.write("home_fan_speed", percent)

    async def async_set_boost_fan_speed(self, percent: int) -> None:
        """Set the configured Boost fan speed."""

        await self.settings.write("boost_fan_speed", percent)

    async def async_set_away_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Away supply air temperature target."""

        await self.settings.write("away_air_temperature_target", celsius)

    async def async_set_home_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Home supply air temperature target."""

        await self.settings.write("home_air_temperature_target", celsius)

    async def async_set_boost_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Boost supply air temperature target."""

        await self.settings.write("boost_air_temperature_target", celsius)

    async def async_set_boost_duration(self, minutes: int) -> None:
        """Set the configured Boost duration."""

        await self.settings.write("boost_duration", minutes)

    async def async_set_fireplace_duration(self, minutes: int) -> None:
        """Set the configured Fireplace duration."""

        await self.settings.write("fireplace_duration", minutes)

    async def async_set_extra_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Extra supply air temperature target."""

        await self.configuration.write("extra_air_temperature_target", celsius)

    async def async_set_extra_extract_fan(self, percent: int) -> None:
        """Set the configured Extra extract fan speed."""

        await self.configuration.write("extra_extract_fan", percent)

    async def async_set_extra_supply_fan(self, percent: int) -> None:
        """Set the configured Extra supply fan speed."""

        await self.configuration.write("extra_supply_fan", percent)

    async def async_set_extra_duration(self, minutes: int) -> None:
        """Set the configured Extra duration."""

        await self.configuration.write("extra_duration", minutes)

    async def async_set_bypass_locked(self, locked: bool) -> None:
        """Set whether heat recovery cell bypass is locked."""

        await self.configuration.write("bypass_locked", locked)
