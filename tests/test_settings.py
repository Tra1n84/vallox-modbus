from __future__ import annotations

from datetime import date

import pytest

from vallox_modbus.settings import ValloxSettings


@pytest.mark.asyncio
async def test_settings_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20499] = [1, 0, 22, 29315]
    mock_modbus_unit.holding[20505] = [1, 1, 35, 29415]
    mock_modbus_unit.holding[20511] = [0, 1, 60, 29515]
    mock_modbus_unit.holding[20544] = [30, 15, 24, 12, 25]

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
    assert settings.filter_changed_day == 24
    assert settings.filter_changed_month == 12
    assert settings.filter_changed_year == 25
    assert settings.filter_change_date == date(2025, 12, 24)


@pytest.mark.asyncio
async def test_setting_reads_stay_inside_safe_ranges(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[20499] = [0] * 4
    mock_modbus_unit.holding[20505] = [0] * 4
    mock_modbus_unit.holding[20511] = [0] * 4
    mock_modbus_unit.holding[20544] = [0] * 5

    settings = ValloxSettings(mock_modbus_unit)
    await settings.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (20499, 4),
        (20505, 4),
        (20511, 4),
        (20544, 5),
    ]


def test_setting_register_ranges_are_explicit() -> None:
    assert ValloxSettings.register_ranges == (
        (20499, 20502),
        (20505, 20508),
        (20511, 20514),
        (20544, 20548),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("day", "month", "year", "expected"),
    [
        (1, 1, 0, date(2000, 1, 1)),
        (31, 12, 99, date(2099, 12, 31)),
        (29, 2, 24, date(2024, 2, 29)),
        (29, 2, 25, None),
        (31, 4, 25, None),
        (0, 1, 25, None),
        (1, 0, 25, None),
        (1, 13, 25, None),
        (32, 1, 25, None),
        (1, 1, 100, None),
        (65535, 65535, 65535, None),
    ],
)
async def test_filter_change_date(
    mock_modbus_unit,
    day: int,
    month: int,
    year: int,
    expected: date | None,
) -> None:
    mock_modbus_unit.holding[20544] = [30, 15, day, month, year]

    settings = ValloxSettings(mock_modbus_unit)
    await settings.async_update()

    assert settings.filter_change_date == expected


def test_filter_change_date_is_none_before_update(mock_modbus_unit) -> None:
    assert ValloxSettings(mock_modbus_unit).filter_change_date is None
