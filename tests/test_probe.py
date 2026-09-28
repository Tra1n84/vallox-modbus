from __future__ import annotations

import pytest
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError

from vallox_modbus import (
    BasicProfile,
    SystemMode,
    ValloxConnectionError,
    ValloxDevice,
    ValloxError,
)


def _seed_probe_registers(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [
        30,
        29425,
        28965,
        29315,
        29375,
        29355,
        0,
        0,
        970,
        1070,
        56,
        0,
    ]
    mock_modbus_unit.holding[4609] = [
        BasicProfile.AWAY,
        SystemMode.NORMAL,
        0,
        0,
        0,
        0,
        0,
        2,
        1,
        100,
        2,
        180,
        0,
    ]


@pytest.mark.asyncio
async def test_probe_returns_device_and_reads_only_measurements_and_runtime(
    mock_modbus_unit,
) -> None:
    _seed_probe_registers(mock_modbus_unit)

    device = await ValloxDevice.async_probe(mock_modbus_unit)

    assert isinstance(device, ValloxDevice)
    assert device.measurements.fan_speed == 30
    assert device.runtime.basic_profile is BasicProfile.AWAY
    assert [
        (event.register_type, event.address, event.count)
        for event in mock_modbus_unit.read_events
    ] == [
        ("holding", 4353, 12),
        ("holding", 4609, 13),
    ]


@pytest.mark.asyncio
async def test_probe_raises_connection_error_on_modbus_timeout(
    mock_modbus_unit,
) -> None:
    _seed_probe_registers(mock_modbus_unit)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timeout"))

    with pytest.raises(ValloxConnectionError):
        await ValloxDevice.async_probe(mock_modbus_unit)


@pytest.mark.asyncio
async def test_probe_raises_connection_error_on_required_group_failure(
    mock_modbus_unit,
) -> None:
    _seed_probe_registers(mock_modbus_unit)
    mock_modbus_unit.fail_read(4609, IllegalDataAddressError())

    with pytest.raises(ValloxConnectionError):
        await ValloxDevice.async_probe(mock_modbus_unit)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("address", "value"),
    [
        (4353, 101),
        (4354, 0),
        (4609, 999),
        (4610, 999),
    ],
)
async def test_probe_raises_vallox_error_on_implausible_values(
    mock_modbus_unit,
    address: int,
    value: int,
) -> None:
    _seed_probe_registers(mock_modbus_unit)
    mock_modbus_unit.holding[address] = value

    with pytest.raises(ValloxError):
        await ValloxDevice.async_probe(mock_modbus_unit)
