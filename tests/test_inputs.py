from __future__ import annotations

import pytest

from vallox_modbus.inputs import ValloxInputs


@pytest.mark.asyncio
async def test_input_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4365] = [1, 0, 75, 123, 456, 789]

    inputs = ValloxInputs(mock_modbus_unit)
    await inputs.async_update()

    assert inputs.fireplace_switch is True
    assert inputs.digital_input is False
    assert inputs.analog_control_input == 75
    assert inputs.multisensor_co2_raw == 123
    assert inputs.multisensor_temperature_raw == 456
    assert inputs.multisensor_humidity_raw == 789


@pytest.mark.asyncio
async def test_input_read_uses_direct_range(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4365] = [0] * 6

    inputs = ValloxInputs(mock_modbus_unit)
    await inputs.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (4365, 6)
    ]


def test_input_register_range_is_explicit() -> None:
    assert ValloxInputs.register_ranges == ((4365, 4370),)
