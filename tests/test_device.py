from __future__ import annotations

import pytest

from vallox_modbus.device import (
    VALLOX_CONNECT_DELAY,
    VALLOX_MESSAGE_SPACING,
    VALLOX_TIMEOUT,
    ValloxDevice,
)
from vallox_modbus.enums import BasicProfile
from vallox_modbus.inputs import ValloxInputs
from vallox_modbus.measurements import ValloxMeasurements
from vallox_modbus.runtime import ValloxRuntime
from vallox_modbus.sensors import ValloxSensors
from vallox_modbus.settings import ValloxSettings


@pytest.mark.asyncio
async def test_device_updates_readings(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [0] * 12
    mock_modbus_unit.holding[4353] = 42
    mock_modbus_unit.holding[4354] = 29315
    mock_modbus_unit.holding[4365] = [0] * 6
    mock_modbus_unit.holding[4372] = [0] * 13
    mock_modbus_unit.holding[4389] = [0] * 6
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4609] = BasicProfile.HOME

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert report.complete is True
    assert report.updated == {"inputs", "measurements", "runtime", "sensors"}
    assert isinstance(device.inputs, ValloxInputs)
    assert isinstance(device.measurements, ValloxMeasurements)
    assert isinstance(device.runtime, ValloxRuntime)
    assert isinstance(device.sensors, ValloxSensors)
    assert isinstance(device.settings, ValloxSettings)
    assert device.measurements.fan_speed == 42
    assert device.measurements.extract_air_temperature == 20.0
    assert device.runtime.basic_profile is BasicProfile.HOME


@pytest.mark.asyncio
async def test_device_updates_settings_separately(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20499] = [1, 0, 22, 29315]
    mock_modbus_unit.holding[20505] = [1, 1, 35, 29415]
    mock_modbus_unit.holding[20511] = [0, 1, 60, 29515]
    mock_modbus_unit.holding[20544] = [30, 15]

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_settings()

    assert report.complete is True
    assert report.updated == {"settings"}
    assert device.settings.away_fan_speed == 22
    assert device.settings.home_fan_speed == 35
    assert device.settings.boost_fan_speed == 60
    assert device.settings.boost_duration == 30
    assert device.settings.fireplace_duration == 15


@pytest.mark.asyncio
async def test_device_update_combines_readings_and_settings(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [0] * 12
    mock_modbus_unit.holding[4365] = [0] * 6
    mock_modbus_unit.holding[4372] = [0] * 13
    mock_modbus_unit.holding[4389] = [0] * 6
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[20499] = [0, 0, 22, 29315]
    mock_modbus_unit.holding[20505] = [0, 0, 35, 29415]
    mock_modbus_unit.holding[20511] = [0, 0, 60, 29515]
    mock_modbus_unit.holding[20544] = [30, 15]

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update()

    assert report.complete is True
    assert report.updated == {
        "inputs",
        "measurements",
        "runtime",
        "sensors",
        "settings",
    }


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
