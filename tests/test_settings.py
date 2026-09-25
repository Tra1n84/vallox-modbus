from __future__ import annotations

import pytest

from vallox_modbus.settings import ValloxSettings


@pytest.mark.asyncio
async def test_settings_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20499] = [1, 0, 22, 29315]
    mock_modbus_unit.holding[20505] = [1, 1, 35, 29415]
    mock_modbus_unit.holding[20511] = [0, 1, 60, 29515]
    mock_modbus_unit.holding[20544] = [30, 15]

    settings = ValloxSettings(mock_modbus_unit)
    await settings.async_update()

    assert settings.away_rh_control_enabled is True
    assert settings.away_co2_control_enabled is False
    assert settings.away_fan_speed == 22
    assert settings.away_air_temperature_target == 20.0
    assert settings.home_rh_control_enabled is True
    assert settings.home_co2_control_enabled is True
    assert settings.home_fan_speed == 35
    assert settings.home_air_temperature_target == 21.0
    assert settings.boost_rh_control_enabled is False
    assert settings.boost_co2_control_enabled is True
    assert settings.boost_fan_speed == 60
    assert settings.boost_air_temperature_target == 22.0
    assert settings.boost_duration == 30
    assert settings.fireplace_duration == 15


@pytest.mark.asyncio
async def test_setting_reads_stay_inside_safe_ranges(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20499] = [0] * 4
    mock_modbus_unit.holding[20505] = [0] * 4
    mock_modbus_unit.holding[20511] = [0] * 4
    mock_modbus_unit.holding[20544] = [0] * 2

    settings = ValloxSettings(mock_modbus_unit)
    await settings.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (20499, 4),
        (20505, 4),
        (20511, 4),
        (20544, 2),
    ]


def test_setting_register_ranges_are_explicit() -> None:
    assert ValloxSettings.register_ranges == (
        (20499, 20502),
        (20505, 20508),
        (20511, 20514),
        (20544, 20545),
    )
