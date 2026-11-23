from __future__ import annotations

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)

from vallox_modbus.device import ValloxDevice


def _seed_readings(unit) -> None:
    unit.holding[4353] = [0] * 12
    unit.holding[4353] = 42
    unit.holding[4365] = [0] * 6
    unit.holding[4372] = [0] * 13
    unit.holding[4389] = [0] * 6
    unit.holding[4609] = [0] * 13
    unit.holding[21766] = [0, 0]
    unit.holding[21772] = 0


def _seed_settings(unit) -> None:
    unit.holding[20482] = [1, 192, 0x0101, 10, 11, 12, 13]
    unit.holding[20493] = [29315, 14, 15, 45]
    unit.holding[20499] = [0, 0, 22, 29315]
    unit.holding[20505] = [0, 0, 35, 29415]
    unit.holding[20511] = [0, 0, 60, 29515]
    unit.holding[20537] = [180, 0, 1, 2]
    unit.holding[20544] = [30, 15, 1, 2, 26]
    unit.holding[20552] = 0


def _fail_holding_reads(unit, address: int, error: Exception, times: int) -> None:
    """Raise ``error`` for the first ``times`` holding reads starting at address."""

    read = unit.read_holding_registers
    remaining = times

    async def failing_read(start: int, count: int) -> list[int]:
        nonlocal remaining
        if start == address and remaining > 0:
            remaining -= 1
            raise error
        return await read(start, count)

    unit.read_holding_registers = failing_read


def _reads_at(unit, address: int) -> int:
    return sum(1 for event in unit.read_events if event.address == address)


@pytest.mark.asyncio
async def test_readings_retry_first_component_after_timeout(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4353, ModbusTimeoutError("timeout"), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert report.complete is True
    assert "measurements" in report.updated
    assert device.measurements.fan_speed == 42
    assert _reads_at(mock_modbus_unit, 4353) == 1


@pytest.mark.asyncio
async def test_readings_raise_when_first_component_retry_times_out(
    mock_modbus_unit,
) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4353, ModbusTimeoutError("timeout"), 2)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update_readings()

    assert device.measurements.fan_speed is None


@pytest.mark.asyncio
async def test_readings_report_later_component_after_failed_retry(
    mock_modbus_unit,
) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4609, ModbusTimeoutError("timeout"), 2)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert set(report.failed) == {"runtime"}
    assert isinstance(report.failed["runtime"], ModbusTimeoutError)
    assert report.updated == {"measurements", "inputs", "sensors", "timer_switches"}


@pytest.mark.asyncio
async def test_readings_retry_later_component_after_timeout(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4609, ModbusTimeoutError("timeout"), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert report.complete is True
    assert "runtime" in report.updated


@pytest.mark.asyncio
async def test_settings_retry_component_after_timeout_in_later_block(
    mock_modbus_unit,
) -> None:
    _seed_settings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 20544, ModbusTimeoutError("timeout"), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_settings()

    assert report.complete is True
    assert report.updated == {"settings", "configuration"}
    assert device.settings.home_fan_speed == 35
    assert device.settings.boost_duration == 30
    assert _reads_at(mock_modbus_unit, 20544) == 1
    assert _reads_at(mock_modbus_unit, 20499) == 2


@pytest.mark.asyncio
async def test_settings_raise_when_retry_times_out(mock_modbus_unit) -> None:
    _seed_settings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 20544, ModbusTimeoutError("timeout"), 2)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update_settings()

    assert device.settings.home_fan_speed is None


@pytest.mark.asyncio
async def test_combined_update_retries_settings_after_timeout(
    mock_modbus_unit,
) -> None:
    _seed_readings(mock_modbus_unit)
    _seed_settings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 20544, ModbusTimeoutError("timeout"), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update()

    assert report.complete is True
    assert {"settings", "configuration"} <= report.updated


@pytest.mark.asyncio
async def test_non_timeout_error_is_not_retried(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.fail_read(4609, IllegalDataAddressError())

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert set(report.failed) == {"runtime"}
    assert _reads_at(mock_modbus_unit, 4609) == 1


@pytest.mark.asyncio
async def test_connection_error_is_not_retried(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4353, ModbusConnectionError("lost"), 1)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusConnectionError):
        await device.async_update_readings()

    assert _reads_at(mock_modbus_unit, 4609) == 0


@pytest.mark.asyncio
async def test_listeners_fire_once_after_retry(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _fail_holding_reads(mock_modbus_unit, 4353, ModbusTimeoutError("timeout"), 1)

    device = ValloxDevice(mock_modbus_unit)
    calls: list[str] = []
    device.measurements.add_update_listener(lambda: calls.append("measurements"))

    await device.async_update_readings()

    assert calls == ["measurements"]
