from __future__ import annotations

import pytest

from vallox_modbus.device import (
    VALLOX_CONNECT_DELAY,
    VALLOX_MESSAGE_SPACING,
    VALLOX_TIMEOUT,
    ValloxDevice,
)
from vallox_modbus.enums import BasicProfile
from vallox_modbus.measurements import ValloxMeasurements
from vallox_modbus.runtime import ValloxRuntime


@pytest.mark.asyncio
async def test_device_updates_readings(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [0] * 12
    mock_modbus_unit.holding[4353] = 42
    mock_modbus_unit.holding[4354] = 29315
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4609] = BasicProfile.HOME

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert report.complete is True
    assert report.updated == {"measurements", "runtime"}
    assert isinstance(device.measurements, ValloxMeasurements)
    assert isinstance(device.runtime, ValloxRuntime)
    assert device.measurements.fan_speed == 42
    assert device.measurements.extract_air_temperature == 20.0
    assert device.runtime.basic_profile is BasicProfile.HOME


def test_device_sets_vallox_timing_requirements() -> None:
    class Unit:
        timeout: float | None = None
        connect_delay: float | None = None
        message_spacing: float | None = None

        def require_timeout(self, seconds: float | None) -> None:
            self.timeout = seconds

        def require_connect_delay(self, seconds: float | None) -> None:
            self.connect_delay = seconds

        def set_message_spacing(self, seconds: float) -> None:
            self.message_spacing = seconds

    unit = Unit()

    ValloxDevice(unit)

    assert unit.timeout == VALLOX_TIMEOUT
    assert unit.connect_delay == VALLOX_CONNECT_DELAY
    assert unit.message_spacing == VALLOX_MESSAGE_SPACING
