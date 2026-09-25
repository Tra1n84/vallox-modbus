from __future__ import annotations

import pytest

from vallox_modbus.enums import SensorLevel
from vallox_modbus.measurements import ValloxMeasurements


@pytest.mark.asyncio
async def test_measurement_decoding(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [
        42,
        29315,
        28135,
        28325,
        29005,
        29175,
        SensorLevel.MEDIUM,
        SensorLevel.HIGH,
        1640,
        1512,
        47,
        650,
    ]

    measurements = ValloxMeasurements(mock_modbus_unit)
    await measurements.async_update()

    assert measurements.fan_speed == 42
    assert measurements.extract_air_temperature == 20.0
    assert measurements.exhaust_air_temperature == pytest.approx(8.2)
    assert measurements.outdoor_air_temperature == pytest.approx(10.1)
    assert measurements.supply_cell_air_temperature == pytest.approx(16.9)
    assert measurements.supply_air_temperature == pytest.approx(18.6)
    assert measurements.rh_level is SensorLevel.MEDIUM
    assert measurements.co2_level is SensorLevel.HIGH
    assert measurements.extract_fan_rpm == 1640
    assert measurements.supply_fan_rpm == 1512
    assert measurements.humidity == 47
    assert measurements.co2 == 650


@pytest.mark.asyncio
async def test_measurement_read_uses_direct_addresses(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [0] * 12
    mock_modbus_unit.holding[4354] = 29315

    measurements = ValloxMeasurements(mock_modbus_unit)
    await measurements.async_update()

    assert measurements.extract_air_temperature == 20.0
    assert [(event.address, event.count) for event in mock_modbus_unit.read_events] == [
        (4353, 12)
    ]


def test_measurement_register_range_is_explicit() -> None:
    assert ValloxMeasurements.register_ranges == ((4353, 4364),)


@pytest.mark.asyncio
async def test_measurement_no_sensor_values(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4353] = [0] * 12

    measurements = ValloxMeasurements(mock_modbus_unit)
    await measurements.async_update()

    assert measurements.humidity is None
    assert measurements.co2 is None
