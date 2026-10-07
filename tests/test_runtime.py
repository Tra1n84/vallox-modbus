from __future__ import annotations

import pytest

from vallox_modbus.enums import BasicProfile, HeatExchangerState, SystemMode
from vallox_modbus.runtime import ValloxRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "profile"),
    [
        (0, BasicProfile.HOME),
        (1, BasicProfile.AWAY),
        (2, BasicProfile.AUTOMATIC),
    ],
)
async def test_basic_profile_decoding(mock_modbus_unit, raw, profile) -> None:
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4609] = raw

    runtime = ValloxRuntime(mock_modbus_unit)
    await runtime.async_update()

    assert runtime.basic_profile is profile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "state"),
    [
        (0, HeatExchangerState.HEAT_RECOVERY),
        (1, HeatExchangerState.COOL_RECOVERY),
        (2, HeatExchangerState.BYPASS),
        (3, HeatExchangerState.DEFROSTING),
    ],
)
async def test_heat_exchanger_state_decoding(mock_modbus_unit, raw, state) -> None:
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4616] = raw

    runtime = ValloxRuntime(mock_modbus_unit)
    await runtime.async_update()

    assert runtime.heat_exchanger_state is state


@pytest.mark.asyncio
async def test_runtime_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4609] = [
        BasicProfile.AUTOMATIC,
        SystemMode.OFF,
        1,
        10,
        20,
        30,
        1,
        HeatExchangerState.BYPASS,
        2,
        1234,
        56,
        81,
        1,
    ]

    runtime = ValloxRuntime(mock_modbus_unit)
    await runtime.async_update()

    assert runtime.basic_profile is BasicProfile.AUTOMATIC
    assert runtime.system_mode is SystemMode.OFF
    assert runtime.defrosting is True
    assert runtime.boost_timer == 10
    assert runtime.fireplace_timer == 20
    assert runtime.extra_timer == 30
    assert runtime.weekly_timer_enabled is True
    assert runtime.heat_exchanger_state is HeatExchangerState.BYPASS
    assert runtime.total_uptime_years == 2
    assert runtime.total_uptime_hours == 1234
    assert runtime.current_uptime_hours == 56
    assert runtime.filter_remaining == 81
    assert runtime.fault is True


@pytest.mark.asyncio
async def test_runtime_read_uses_direct_range(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4609] = [0] * 13

    runtime = ValloxRuntime(mock_modbus_unit)
    await runtime.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (4609, 13)
    ]


def test_runtime_register_range_is_explicit() -> None:
    assert ValloxRuntime.register_ranges == ((4609, 4621),)
