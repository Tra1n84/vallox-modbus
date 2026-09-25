"""Top-level Vallox Modbus device object."""

from __future__ import annotations

from typing import Final

from modbus_connection import ModbusUnit
from modbus_connection.model import Device, UpdateReport

from .measurements import ValloxMeasurements
from .runtime import ValloxRuntime

VALLOX_TIMEOUT: Final = 5.0
VALLOX_CONNECT_DELAY: Final = 0.5
VALLOX_MESSAGE_SPACING: Final = 0.15


class ValloxDevice(Device):
    """Read-only Vallox MV device model."""

    measurements: ValloxMeasurements
    runtime: ValloxRuntime

    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        unit.require_timeout(VALLOX_TIMEOUT)
        unit.require_connect_delay(VALLOX_CONNECT_DELAY)
        unit.set_message_spacing(VALLOX_MESSAGE_SPACING)
        self.measurements = ValloxMeasurements(unit)
        self.runtime = ValloxRuntime(unit)

    async def async_update_readings(self) -> UpdateReport:
        """Update all read-only V1 readings."""

        return await self.async_poll(("measurements", "runtime"))
