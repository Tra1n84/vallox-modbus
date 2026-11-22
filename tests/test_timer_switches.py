from __future__ import annotations

import pytest

from vallox_modbus import ValloxDevice, ValloxTimerSwitches


@pytest.mark.asyncio
async def test_timer_switch_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[21766] = [1, 0]
    mock_modbus_unit.holding[21772] = 1

    switches = ValloxTimerSwitches(mock_modbus_unit)
    await switches.async_update()

    assert switches.boost_timer_enabled is True
    assert switches.fireplace_timer_enabled is False
    assert switches.extra_timer_enabled is True


@pytest.mark.asyncio
async def test_timer_switch_reads_skip_undocumented_registers(
    mock_modbus_unit,
) -> None:
    switches = ValloxTimerSwitches(mock_modbus_unit)
    await switches.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (21766, 2),
        (21772, 1),
    ]


def test_timer_switch_register_ranges_are_explicit() -> None:
    assert ValloxTimerSwitches.register_ranges == (
        (21766, 21767),
        (21772, 21772),
    )


@pytest.mark.asyncio
async def test_timer_switches_are_part_of_readings_not_settings(
    mock_modbus_unit,
) -> None:
    device = ValloxDevice(mock_modbus_unit)

    await device.async_update_settings()
    settings_reads = {event.address for event in mock_modbus_unit.read_events}
    mock_modbus_unit.read_events.clear()
    await device.async_update_readings()
    reading_reads = {event.address for event in mock_modbus_unit.read_events}

    assert {21766, 21772}.isdisjoint(settings_reads)
    assert {21766, 21772} <= reading_reads
