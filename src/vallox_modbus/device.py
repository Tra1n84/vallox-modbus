"""Top-level Vallox Modbus device object."""

from __future__ import annotations

from typing import Final

from modbus_connection import ModbusUnit
from modbus_connection.model import Device, UpdateReport

from .configuration import ValloxConfiguration
from .inputs import ValloxInputs
from .measurements import ValloxMeasurements
from .runtime import ValloxRuntime
from .sensors import ValloxSensors
from .settings import ValloxSettings

VALLOX_TIMEOUT: Final = 5.0
VALLOX_CONNECT_DELAY: Final = 0.5
VALLOX_MESSAGE_SPACING: Final = 0.15


class ValloxDevice(Device):
    """Read-only Vallox MV device model."""

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
