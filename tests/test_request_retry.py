from __future__ import annotations

import logging

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    IllegalDataValueError,
    ModbusConnectionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)

from vallox_modbus import (
    Profile,
    ValloxConnectionError,
    ValloxDevice,
    ValloxPartialWriteError,
)
from vallox_modbus.device import VALLOX_REQUEST_RETRIES
from vallox_modbus.retry import TimeoutRetryingUnit

MAX_ATTEMPTS = VALLOX_REQUEST_RETRIES + 1


def _seed_readings(unit) -> None:
    unit.holding[4353] = [0] * 12
    unit.holding[4353] = 42
    unit.holding[4365] = [0] * 6
    unit.holding[4372] = [0] * 13
    unit.holding[4389] = [0] * 6
    unit.holding[4609] = [0] * 13
    unit.holding[21766] = [0, 0]
    unit.holding[21772] = 0


def _seed_settings(unit) -> None:
    unit.holding[20482] = [1, 192, 0x0101, 10, 11, 12, 13]
    unit.holding[20493] = [29315, 14, 15, 45]
    unit.holding[20499] = [0, 0, 22, 29315]
    unit.holding[20505] = [0, 0, 35, 29415]
    unit.holding[20511] = [0, 0, 60, 29515]
    unit.holding[20537] = [180, 0, 1, 2]
    unit.holding[20544] = [30, 15, 1, 2, 26]
    unit.holding[20552] = 0


class _Flaky:
    """Make ``method`` raise ``error`` for requests to ``address``.

    The first ``times`` requests fail, or every request if ``times`` is None.
    ``attempts`` counts every request sent to ``address``.
    """

    def __init__(
        self,
        unit,
        method: str,
        address: int,
        error: Exception,
        times: int | None,
    ) -> None:
        self.attempts = 0
        original = getattr(unit, method)

        async def flaky(start: int, *args):
            if start == address:
                self.attempts += 1
                if times is None or self.attempts <= times:
                    raise error
            return await original(start, *args)

        setattr(unit, method, flaky)


def _timeout() -> ModbusTimeoutError:
    return ModbusTimeoutError("Response timeout after 1.0 seconds")


def _capture_writes(unit) -> list:
    events = []
    unit.on_write(events.append)
    return events


def _written(events) -> list[tuple[int, list[int]]]:
    return [(event.address, event.values) for event in events]


def _reads_at(unit, address: int) -> int:
    return sum(1 for event in unit.read_events if event.address == address)


# -- reads ---------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("times", range(1, MAX_ATTEMPTS))
async def test_read_succeeds_after_timeouts(mock_modbus_unit, times: int) -> None:
    _seed_readings(mock_modbus_unit)
    flaky = _Flaky(mock_modbus_unit, "read_holding_registers", 4353, _timeout(), times)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert report.complete is True
    assert device.measurements.fan_speed == 42
    assert flaky.attempts == times + 1


@pytest.mark.asyncio
async def test_read_retries_only_the_timed_out_block(mock_modbus_unit) -> None:
    _seed_settings(mock_modbus_unit)
    flaky = _Flaky(mock_modbus_unit, "read_holding_registers", 20505, _timeout(), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_settings()

    assert report.complete is True
    assert report.updated == {"settings", "configuration"}
    assert device.settings.home_fan_speed == 35
    assert flaky.attempts == 2
    assert _reads_at(mock_modbus_unit, 20499) == 1
    assert _reads_at(mock_modbus_unit, 20511) == 1


@pytest.mark.asyncio
async def test_unreachable_device_aborts_after_first_request(
    mock_modbus_unit,
) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.fail_requests(_timeout())

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update_readings()

    assert [event.address for event in mock_modbus_unit.read_events] == [
        4353
    ] * MAX_ATTEMPTS
    assert device.measurements.fan_speed is None


@pytest.mark.asyncio
async def test_unreachable_device_aborts_settings_after_first_request(
    mock_modbus_unit,
) -> None:
    _seed_settings(mock_modbus_unit)
    mock_modbus_unit.fail_requests(_timeout())

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update_settings()

    assert len(mock_modbus_unit.read_events) == MAX_ATTEMPTS
    assert {event.address for event in mock_modbus_unit.read_events} == {20499}


@pytest.mark.asyncio
async def test_persistent_timeout_after_answer_is_reported(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.fail_read(4609, _timeout())

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert set(report.failed) == {"runtime"}
    assert isinstance(report.failed["runtime"], ModbusTimeoutError)
    assert report.updated == {"measurements", "inputs", "sensors", "timer_switches"}
    assert _reads_at(mock_modbus_unit, 4609) == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_combined_update_retries_settings_request(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _seed_settings(mock_modbus_unit)
    flaky = _Flaky(mock_modbus_unit, "read_holding_registers", 20544, _timeout(), 1)

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update()

    assert report.complete is True
    assert {"settings", "configuration"} <= report.updated
    assert flaky.attempts == 2


@pytest.mark.asyncio
async def test_exception_response_is_not_retried(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.fail_read(4609, IllegalDataAddressError())

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert set(report.failed) == {"runtime"}
    assert _reads_at(mock_modbus_unit, 4609) == 1


@pytest.mark.asyncio
async def test_protocol_error_is_not_retried(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.fail_read(4609, ModbusProtocolError("bad frame"))

    device = ValloxDevice(mock_modbus_unit)
    report = await device.async_update_readings()

    assert set(report.failed) == {"runtime"}
    assert _reads_at(mock_modbus_unit, 4609) == 1


@pytest.mark.asyncio
async def test_connection_error_is_not_retried(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    flaky = _Flaky(
        mock_modbus_unit,
        "read_holding_registers",
        4353,
        ModbusConnectionError("lost"),
        None,
    )

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ModbusConnectionError):
        await device.async_update_readings()

    assert flaky.attempts == 1
    assert _reads_at(mock_modbus_unit, 4609) == 0


@pytest.mark.asyncio
async def test_listeners_fire_once_after_retry(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    _Flaky(mock_modbus_unit, "read_holding_registers", 4353, _timeout(), 1)

    device = ValloxDevice(mock_modbus_unit)
    calls: list[str] = []
    device.measurements.add_update_listener(lambda: calls.append("measurements"))

    await device.async_update_readings()

    assert calls == ["measurements"]


@pytest.mark.asyncio
async def test_probe_retries_timed_out_request(mock_modbus_unit) -> None:
    _seed_readings(mock_modbus_unit)
    mock_modbus_unit.holding[4354] = [29315] * 5
    flaky = _Flaky(mock_modbus_unit, "read_holding_registers", 4609, _timeout(), 1)

    device = await ValloxDevice.async_probe(mock_modbus_unit)

    assert device.measurements.fan_speed == 42
    assert flaky.attempts == 2


# -- writes --------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("times", range(1, MAX_ATTEMPTS))
async def test_write_succeeds_after_timeouts(mock_modbus_unit, times: int) -> None:
    flaky = _Flaky(mock_modbus_unit, "write_register", 4610, _timeout(), times)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    await device.async_set_power(False)

    assert _written(events) == [(4610, [5])]
    assert flaky.attempts == times + 1


@pytest.mark.asyncio
async def test_fc16_write_succeeds_after_timeout(mock_modbus_unit) -> None:
    flaky = _Flaky(mock_modbus_unit, "write_registers", 20545, _timeout(), 1)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    await device.async_set_fireplace_duration(15)

    assert [(e.address, e.values, e.function_code) for e in events] == [
        (20545, [15], 0x10)
    ]
    assert flaky.attempts == 2


@pytest.mark.asyncio
async def test_write_raises_after_persistent_timeout(mock_modbus_unit) -> None:
    error = _timeout()
    flaky = _Flaky(mock_modbus_unit, "write_register", 4610, error, None)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ValloxConnectionError) as exc_info:
        await device.async_set_power(True)

    assert exc_info.value.__cause__ is error
    assert flaky.attempts == MAX_ATTEMPTS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [IllegalDataValueError(), ModbusConnectionError("lost")],
)
async def test_write_error_other_than_timeout_is_not_retried(
    mock_modbus_unit, error: Exception
) -> None:
    flaky = _Flaky(mock_modbus_unit, "write_register", 4610, error, None)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ValloxConnectionError) as exc_info:
        await device.async_set_power(True)

    assert exc_info.value.__cause__ is error
    assert flaky.attempts == 1


# -- profile sequence ----------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_sequence_retries_timed_out_step(mock_modbus_unit) -> None:
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4612] = 30
    flaky = _Flaky(mock_modbus_unit, "write_register", 4612, _timeout(), 1)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    await device.async_set_profile(Profile.AWAY)

    assert _written(events) == [
        (4609, [1]),
        (4612, [0]),
        (4613, [0]),
        (4614, [0]),
    ]
    assert flaky.attempts == 2


@pytest.mark.asyncio
async def test_profile_sequence_retries_timer_switch_step(mock_modbus_unit) -> None:
    flaky = _Flaky(mock_modbus_unit, "write_register", 21766, _timeout(), 2)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    await device.async_set_profile(Profile.BOOST, 30)

    assert _written(events) == [
        (4612, [30]),
        (21766, [1]),
        (4613, [0]),
        (4614, [0]),
    ]
    assert flaky.attempts == 3


@pytest.mark.asyncio
async def test_profile_sequence_retries_configured_duration_read(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.holding[20544] = 45
    flaky = _Flaky(mock_modbus_unit, "read_holding_registers", 20544, _timeout(), 1)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    await device.async_set_profile(Profile.BOOST)

    assert _written(events)[0] == (4612, [45])
    assert flaky.attempts == 2


@pytest.mark.asyncio
async def test_profile_sequence_partial_after_persistent_timeout(
    mock_modbus_unit,
) -> None:
    error = _timeout()
    flaky = _Flaky(mock_modbus_unit, "write_register", 4612, error, None)
    events = _capture_writes(mock_modbus_unit)

    device = ValloxDevice(mock_modbus_unit)
    with pytest.raises(ValloxPartialWriteError) as exc_info:
        await device.async_set_profile(Profile.AWAY)

    assert exc_info.value.__cause__ is error
    assert exc_info.value.completed == (4609,)
    assert exc_info.value.failed == 4612
    assert _written(events) == [(4609, [1])]
    assert flaky.attempts == MAX_ATTEMPTS


# -- logging and wrapper -------------------------------------------------------


@pytest.mark.asyncio
async def test_each_retry_is_logged_at_debug_level(
    mock_modbus_unit, caplog: pytest.LogCaptureFixture
) -> None:
    _Flaky(mock_modbus_unit, "write_register", 4612, _timeout(), 2)
    device = ValloxDevice(mock_modbus_unit)

    with caplog.at_level(logging.DEBUG, logger="vallox_modbus"):
        await device.async_set_boost_timer(0)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "vallox_modbus.retry"
    ]
    assert all(
        record.levelno == logging.DEBUG
        for record in caplog.records
        if record.name == "vallox_modbus.retry"
    )
    assert messages == [
        "write_register(4612, 0) timed out, retrying "
        f"(attempt 2 of {MAX_ATTEMPTS}): Response timeout after 1.0 seconds",
        "write_register(4612, 0) timed out, retrying "
        f"(attempt 3 of {MAX_ATTEMPTS}): Response timeout after 1.0 seconds",
    ]


@pytest.mark.asyncio
async def test_successful_request_is_not_logged(
    mock_modbus_unit, caplog: pytest.LogCaptureFixture
) -> None:
    device = ValloxDevice(mock_modbus_unit)

    with caplog.at_level(logging.DEBUG, logger="vallox_modbus"):
        await device.async_set_boost_timer(0)

    assert not [r for r in caplog.records if r.name == "vallox_modbus.retry"]


def test_wrapper_delegates_other_attributes(mock_modbus_unit) -> None:
    wrapper = TimeoutRetryingUnit(mock_modbus_unit, 3)

    wrapper.set_message_spacing(0.25)

    assert mock_modbus_unit.message_spacing == 0.25
    assert wrapper.connected is mock_modbus_unit.connected


def test_wrapper_rejects_negative_retries(mock_modbus_unit) -> None:
    with pytest.raises(ValueError):
        TimeoutRetryingUnit(mock_modbus_unit, -1)
