from __future__ import annotations

import pytest

from vallox_modbus.configuration import ValloxConfiguration
from vallox_modbus.enums import HeaterType, HeatRecoveryCellType, ModbusParity


@pytest.mark.asyncio
async def test_configuration_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20482] = [1, 192, 0x0101, 10, 11, 12, 13]
    mock_modbus_unit.holding[20493] = [29315, 14, 15, 45]
    mock_modbus_unit.holding[20537] = [
        180,
        HeatRecoveryCellType.ENTHALPY,
        HeaterType.ELECTRIC,
        HeaterType.WATER,
    ]

    configuration = ValloxConfiguration(mock_modbus_unit)
    await configuration.async_update()

    assert configuration.modbus_address == 1
    assert configuration.modbus_baud_x100 == 192
    assert configuration.modbus_baudrate == 19200
    assert configuration.modbus_frame == 0x0101
    assert configuration.modbus_parity is ModbusParity.EVEN
    assert configuration.modbus_stop_bits == 1
    assert configuration.extract_fan_balance_base == 10
    assert configuration.supply_fan_balance_base == 11
    assert configuration.fireplace_extract_fan == 12
    assert configuration.fireplace_supply_fan == 13
    assert configuration.extra_air_temperature_target == 20.0
    assert configuration.extra_extract_fan == 14
    assert configuration.extra_supply_fan == 15
    assert configuration.extra_time == 45
    assert configuration.filter_change_interval == 180
    assert configuration.heat_recovery_cell_type is HeatRecoveryCellType.ENTHALPY
    assert configuration.extra_heater_type is HeaterType.ELECTRIC
    assert configuration.post_heater_type is HeaterType.WATER


@pytest.mark.asyncio
async def test_configuration_unknown_frame_parts(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20482] = [1, 192, 0x0909, 0, 0, 0, 0]
    mock_modbus_unit.holding[20493] = [29315, 0, 0, 1]
    mock_modbus_unit.holding[20537] = [180, 0, 0, 0]

    configuration = ValloxConfiguration(mock_modbus_unit)
    await configuration.async_update()

    assert configuration.modbus_parity is None
    assert configuration.modbus_stop_bits is None


@pytest.mark.asyncio
async def test_configuration_reads_stay_inside_safe_ranges(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20482] = [0] * 7
    mock_modbus_unit.holding[20493] = [0] * 4
    mock_modbus_unit.holding[20537] = [0] * 4

    configuration = ValloxConfiguration(mock_modbus_unit)
    await configuration.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (20482, 7),
        (20493, 4),
        (20537, 4),
    ]


def test_configuration_register_ranges_are_explicit() -> None:
    assert ValloxConfiguration.register_ranges == (
        (20482, 20488),
        (20493, 20496),
        (20537, 20540),
    )
