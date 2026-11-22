from __future__ import annotations

import pytest
from modbus_connection import IllegalDataValueError, ModbusTimeoutError

from vallox_modbus import (
    BasicProfile,
    ValloxConnectionError,
    ValloxDevice,
    ValloxInvalidInputError,
)
from vallox_modbus.measurements import ValloxMeasurements


def _capture_writes(mock_modbus_unit) -> list:
    events = []
    mock_modbus_unit.on_write(events.append)
    return events


def _writes(events) -> list[tuple[int, list[int], int]]:
    return [(event.address, event.values, event.function_code) for event in events]


@pytest.mark.asyncio
async def test_device_writes_runtime_controls(mock_modbus_unit) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_power(False)
    await device.async_set_power(True)
    await device.async_set_basic_profile(BasicProfile.AWAY)
    await device.async_set_basic_profile(BasicProfile.AUTOMATIC)
    await device.async_set_boost_timer(10)
    await device.async_set_fireplace_timer(20)
    await device.async_set_extra_timer(30)

    assert _writes(events) == [
        (4610, [5], 0x06),
        (4610, [0], 0x06),
        (4609, [1], 0x06),
        (4609, [2], 0x06),
        (4612, [10], 0x06),
        (4613, [20], 0x06),
        (4614, [30], 0x06),
    ]


@pytest.mark.asyncio
async def test_device_writes_profile_settings(mock_modbus_unit) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_away_fan_speed(30)
    await device.async_set_home_fan_speed(60)
    await device.async_set_boost_fan_speed(90)
    await device.async_set_away_air_temperature_target(15.0)
    await device.async_set_home_air_temperature_target(13.0)
    await device.async_set_boost_air_temperature_target(15.0)
    await device.async_set_boost_duration(30)
    await device.async_set_fireplace_duration(15)

    assert _writes(events) == [
        (20501, [30], 0x06),
        (20507, [60], 0x06),
        (20513, [90], 0x06),
        (20502, [28815], 0x06),
        (20508, [28615], 0x06),
        (20514, [28815], 0x06),
        (20544, [30], 0x06),
        (20545, [15], 0x10),
    ]


@pytest.mark.asyncio
async def test_device_writes_extra_settings(mock_modbus_unit) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_extra_air_temperature_target(15.0)
    await device.async_set_extra_extract_fan(50)
    await device.async_set_extra_supply_fan(51)
    await device.async_set_extra_duration(10)
    await device.async_set_bypass_locked(True)

    assert _writes(events) == [
        (20493, [28815], 0x06),
        (20494, [50], 0x06),
        (20495, [51], 0x06),
        (20496, [10], 0x06),
        (20552, [1], 0x06),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "value"),
    [
        ("async_set_home_fan_speed", -1),
        ("async_set_home_fan_speed", 101),
        ("async_set_home_air_temperature_target", 4.9),
        ("async_set_home_air_temperature_target", 25.1),
        ("async_set_boost_duration", 0),
        ("async_set_fireplace_duration", 0),
        ("async_set_boost_timer", -1),
        ("async_set_basic_profile", 3),
        ("async_set_bypass_locked", 1),
        ("async_set_home_fan_speed", 50.5),
        ("async_set_home_fan_speed", "abc"),
        ("async_set_home_fan_speed", None),
        ("async_set_extra_duration", 65536),
        ("async_set_extra_air_temperature_target", "warm"),
    ],
)
async def test_device_rejects_out_of_range_writes(
    mock_modbus_unit,
    method_name: str,
    value: int | float,
) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxInvalidInputError) as exc_info:
        await getattr(device, method_name)(value)

    assert isinstance(exc_info.value, ValueError)
    assert events == []


@pytest.mark.asyncio
async def test_read_only_fields_are_not_writable(mock_modbus_unit) -> None:
    events = _capture_writes(mock_modbus_unit)
    measurements = ValloxMeasurements(mock_modbus_unit)

    with pytest.raises(AttributeError):
        await measurements.write("fan_speed", 50)

    assert events == []


SETTER_CALLS = [
    ("async_set_power", True, 4610),
    ("async_set_basic_profile", BasicProfile.HOME, 4609),
    ("async_set_boost_timer", 10, 4612),
    ("async_set_fireplace_timer", 10, 4613),
    ("async_set_extra_timer", 10, 4614),
    ("async_set_away_fan_speed", 30, 20501),
    ("async_set_home_fan_speed", 60, 20507),
    ("async_set_boost_fan_speed", 90, 20513),
    ("async_set_away_air_temperature_target", 15.0, 20502),
    ("async_set_home_air_temperature_target", 15.0, 20508),
    ("async_set_boost_air_temperature_target", 15.0, 20514),
    ("async_set_boost_duration", 30, 20544),
    ("async_set_fireplace_duration", 15, 20545),
    ("async_set_extra_air_temperature_target", 15.0, 20493),
    ("async_set_extra_extract_fan", 50, 20494),
    ("async_set_extra_supply_fan", 50, 20495),
    ("async_set_extra_duration", 10, 20496),
    ("async_set_bypass_locked", True, 20552),
]


def test_setter_error_mapping_covers_all_setters() -> None:
    setters = {
        name
        for name in dir(ValloxDevice)
        if name.startswith("async_set_") and name != "async_set_profile"
    }

    assert setters == {name for name, _, _ in SETTER_CALLS}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [ModbusTimeoutError("timeout"), IllegalDataValueError()]
)
@pytest.mark.parametrize(("method_name", "value", "address"), SETTER_CALLS)
async def test_setters_map_modbus_errors(
    mock_modbus_unit,
    method_name: str,
    value: object,
    address: int,
    error: Exception,
) -> None:
    mock_modbus_unit.fail_write(address, error)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxConnectionError) as exc_info:
        await getattr(device, method_name)(value)

    assert exc_info.value.__cause__ is error
