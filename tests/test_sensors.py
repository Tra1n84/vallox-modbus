from __future__ import annotations

import pytest

from vallox_modbus.sensors import NO_SENSOR, ValloxSensors


@pytest.mark.asyncio
async def test_sensor_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4372] = [
        1922,
        41,
        NO_SENSOR,
        43,
        44,
        45,
        46,
        500,
        NO_SENSOR,
        700,
        800,
        900,
        1000,
    ]
    mock_modbus_unit.holding[4389] = [
        29315,
        1000,
        1100,
        NO_SENSOR,
        1300,
        1400,
    ]

    sensors = ValloxSensors(mock_modbus_unit)
    await sensors.async_update()

    assert sensors.internal_humidity_sensor == pytest.approx(49.985)
    assert sensors.rh_sensor_0 == 41
    assert sensors.rh_sensor_1 is None
    assert sensors.rh_sensor_5 == 46
    assert sensors.co2_sensor_0 == 500
    assert sensors.co2_sensor_1 is None
    assert sensors.co2_sensor_5 == 1000
    assert sensors.optional_temperature == 20.0
    assert sensors.voc_level == 1000
    assert sensors.voc_sensor_0 == 1100
    assert sensors.voc_sensor_1 is None
    assert sensors.voc_sensor_3 == 1400


@pytest.mark.asyncio
async def test_sensor_reads_do_not_cross_documented_gap(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4372] = [0] * 13
    mock_modbus_unit.holding[4389] = [0] * 6

    sensors = ValloxSensors(mock_modbus_unit)
    await sensors.async_update()

    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (4372, 13),
        (4389, 6),
    ]


def test_sensor_register_ranges_are_explicit() -> None:
    assert ValloxSensors.register_ranges == (
        (4372, 4384),
        (4389, 4394),
    )
