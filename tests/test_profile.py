from __future__ import annotations

import itertools

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    IllegalDataValueError,
    ModbusTimeoutError,
)

from vallox_modbus import (
    BasicProfile,
    Profile,
    ValloxConnectionError,
    ValloxDevice,
    ValloxError,
    ValloxInvalidInputError,
    ValloxPartialWriteError,
)

FC06 = 0x06


def _capture_writes(mock_modbus_unit) -> list:
    events = []
    mock_modbus_unit.on_write(events.append)
    return events


def _writes(events) -> list[tuple[int, list[int], int]]:
    return [(event.address, event.values, event.function_code) for event in events]


def _reads(mock_modbus_unit) -> list[tuple[int, int]]:
    return [(event.address, event.count) for event in mock_modbus_unit.read_events]


async def _device_with_state(
    mock_modbus_unit,
    *,
    basic_profile: int = BasicProfile.HOME,
    boost_timer: int = 0,
    fireplace_timer: int = 0,
    extra_timer: int = 0,
    switches: tuple[int, int, int] = (1, 1, 1),
) -> ValloxDevice:
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4609] = int(basic_profile)
    mock_modbus_unit.holding[4612] = [boost_timer, fireplace_timer, extra_timer]
    mock_modbus_unit.holding[21766] = [switches[0], switches[1]]
    mock_modbus_unit.holding[21772] = switches[2]
    device = ValloxDevice(mock_modbus_unit)
    await device.runtime.async_update()
    await device.timer_switches.async_update()
    return device


# -- L1: effective profile ----------------------------------------------------


def _expected_profile(
    basic_profile: BasicProfile, boost: int, fireplace: int, extra: int
) -> Profile:
    if extra:
        return Profile.EXTRA
    if fireplace:
        return Profile.FIREPLACE
    if boost:
        return Profile.BOOST
    return {
        BasicProfile.HOME: Profile.HOME,
        BasicProfile.AWAY: Profile.AWAY,
        BasicProfile.AUTOMATIC: Profile.AUTOMATIC,
    }[basic_profile]


@pytest.mark.asyncio
@pytest.mark.parametrize("basic_profile", list(BasicProfile))
@pytest.mark.parametrize(
    ("boost", "fireplace", "extra"),
    list(itertools.product((0, 10, 65535), repeat=3)),
)
async def test_profile_follows_documented_priority(
    mock_modbus_unit,
    basic_profile: BasicProfile,
    boost: int,
    fireplace: int,
    extra: int,
) -> None:
    device = await _device_with_state(
        mock_modbus_unit,
        basic_profile=basic_profile,
        boost_timer=boost,
        fireplace_timer=fireplace,
        extra_timer=extra,
    )

    assert device.profile is _expected_profile(basic_profile, boost, fireplace, extra)


@pytest.mark.asyncio
async def test_profile_ignores_timer_switches(mock_modbus_unit) -> None:
    device = await _device_with_state(
        mock_modbus_unit, boost_timer=10, switches=(0, 0, 0)
    )

    assert device.profile is Profile.BOOST


def test_profile_is_none_before_runtime_update(mock_modbus_unit) -> None:
    device = ValloxDevice(mock_modbus_unit)

    assert device.profile is None
    assert device.remaining_profile_duration is None


@pytest.mark.asyncio
async def test_profile_is_none_for_unknown_basic_profile(mock_modbus_unit) -> None:
    device = await _device_with_state(mock_modbus_unit, basic_profile=7)

    assert device.runtime.basic_profile is None
    assert device.profile is None


@pytest.mark.asyncio
async def test_profile_uses_timer_before_unknown_basic_profile(
    mock_modbus_unit,
) -> None:
    device = await _device_with_state(
        mock_modbus_unit, basic_profile=7, fireplace_timer=5
    )

    assert device.profile is Profile.FIREPLACE


def test_profile_enum_is_separate_from_basic_profile() -> None:
    assert Profile is not BasicProfile
    assert [profile.name for profile in Profile] == [
        "HOME",
        "AWAY",
        "AUTOMATIC",
        "BOOST",
        "FIREPLACE",
        "EXTRA",
    ]


# -- L5: remaining profile duration ---------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timer", "switch", "expected"),
    [
        (0, 1, 0),
        (0, 0, 0),
        (25, 1, 25),
        (25, 0, None),
        (65535, 1, None),
        (65535, 0, None),
    ],
)
@pytest.mark.parametrize(
    ("profile", "index"),
    [(Profile.BOOST, 0), (Profile.FIREPLACE, 1), (Profile.EXTRA, 2)],
)
async def test_remaining_profile_duration_semantics(
    mock_modbus_unit,
    profile: Profile,
    index: int,
    timer: int,
    switch: int,
    expected: int | None,
) -> None:
    timers = [0, 0, 0]
    timers[index] = timer
    switches = [1, 1, 1]
    switches[index] = switch
    device = await _device_with_state(
        mock_modbus_unit,
        boost_timer=timers[0],
        fireplace_timer=timers[1],
        extra_timer=timers[2],
        switches=tuple(switches),
    )

    assert device.get_remaining_profile_duration(profile) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", [Profile.HOME, Profile.AWAY, Profile.AUTOMATIC])
async def test_remaining_profile_duration_is_none_without_timer(
    mock_modbus_unit, profile: Profile
) -> None:
    device = await _device_with_state(mock_modbus_unit, boost_timer=10)

    assert device.get_remaining_profile_duration(profile) is None


@pytest.mark.asyncio
async def test_remaining_profile_duration_with_unread_switches(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.holding[4609] = [0] * 13
    mock_modbus_unit.holding[4612] = 12
    device = ValloxDevice(mock_modbus_unit)
    await device.runtime.async_update()

    assert device.timer_switches.boost_timer_enabled is None
    assert device.get_remaining_profile_duration(Profile.BOOST) == 12


@pytest.mark.asyncio
async def test_remaining_profile_duration_of_active_profile(mock_modbus_unit) -> None:
    device = await _device_with_state(
        mock_modbus_unit, boost_timer=30, fireplace_timer=12
    )

    assert device.profile is Profile.FIREPLACE
    assert device.remaining_profile_duration == 12


@pytest.mark.asyncio
async def test_remaining_profile_duration_of_basic_profile(mock_modbus_unit) -> None:
    device = await _device_with_state(mock_modbus_unit)

    assert device.profile is Profile.HOME
    assert device.remaining_profile_duration is None


@pytest.mark.parametrize("profile", [3, BasicProfile.AWAY, "BOOST", None])
def test_remaining_profile_duration_rejects_non_profile(
    mock_modbus_unit, profile: object
) -> None:
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxInvalidInputError):
        device.get_remaining_profile_duration(profile)


# -- L2: coordinated profile change -------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "value"),
    [(Profile.HOME, 0), (Profile.AWAY, 1), (Profile.AUTOMATIC, 2)],
)
async def test_set_basic_profile_clears_all_timers(
    mock_modbus_unit, profile: Profile, value: int
) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_profile(profile)

    assert _writes(events) == [
        (4609, [value], FC06),
        (4612, [0], FC06),
        (4613, [0], FC06),
        (4614, [0], FC06),
    ]
    assert mock_modbus_unit.read_events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "duration", "expected"),
    [
        (
            Profile.BOOST,
            30,
            [
                (4612, [30], FC06),
                (21766, [1], FC06),
                (4613, [0], FC06),
                (4614, [0], FC06),
            ],
        ),
        (
            Profile.FIREPLACE,
            15,
            [
                (4613, [15], FC06),
                (21767, [1], FC06),
                (4612, [0], FC06),
                (4614, [0], FC06),
            ],
        ),
        (
            Profile.EXTRA,
            1,
            [
                (4614, [1], FC06),
                (21772, [1], FC06),
                (4612, [0], FC06),
                (4613, [0], FC06),
            ],
        ),
        (
            Profile.BOOST,
            65535,
            [(4612, [65535], FC06), (4613, [0], FC06), (4614, [0], FC06)],
        ),
        (
            Profile.FIREPLACE,
            65535,
            [(4613, [65535], FC06), (4612, [0], FC06), (4614, [0], FC06)],
        ),
        (
            Profile.EXTRA,
            65535,
            [(4614, [65535], FC06), (4612, [0], FC06), (4613, [0], FC06)],
        ),
    ],
)
async def test_set_timed_profile_with_duration(
    mock_modbus_unit,
    profile: Profile,
    duration: int,
    expected: list[tuple[int, list[int], int]],
) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_profile(profile, duration)

    assert _writes(events) == expected
    assert mock_modbus_unit.read_events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "duration_address", "expected"),
    [
        (
            Profile.BOOST,
            20544,
            [(4612, [45], FC06), (4613, [0], FC06), (4614, [0], FC06)],
        ),
        (
            Profile.FIREPLACE,
            20545,
            [(4613, [45], FC06), (4612, [0], FC06), (4614, [0], FC06)],
        ),
        (
            Profile.EXTRA,
            20496,
            [(4614, [45], FC06), (4612, [0], FC06), (4613, [0], FC06)],
        ),
    ],
)
async def test_set_timed_profile_reads_configured_duration(
    mock_modbus_unit,
    profile: Profile,
    duration_address: int,
    expected: list[tuple[int, list[int], int]],
) -> None:
    mock_modbus_unit.holding[duration_address] = 45
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    await device.async_set_profile(profile)

    assert _reads(mock_modbus_unit) == [(duration_address, 1)]
    assert _writes(events) == expected


@pytest.mark.asyncio
async def test_set_timed_profile_rereads_configured_duration(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.holding[20499] = [0] * 4
    mock_modbus_unit.holding[20505] = [0] * 4
    mock_modbus_unit.holding[20511] = [0] * 4
    mock_modbus_unit.holding[20544] = [30, 15, 1, 1, 25]
    device = ValloxDevice(mock_modbus_unit)
    await device.settings.async_update()
    mock_modbus_unit.holding[20544] = 60
    mock_modbus_unit.read_events.clear()
    events = _capture_writes(mock_modbus_unit)

    await device.async_set_profile(Profile.BOOST)

    assert device.settings.boost_duration == 30
    assert _reads(mock_modbus_unit) == [(20544, 1)]
    assert _writes(events)[0] == (4612, [60], FC06)


@pytest.mark.asyncio
async def test_set_timed_profile_rejects_implausible_configured_duration(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.holding[20544] = 0
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxError) as exc_info:
        await device.async_set_profile(Profile.BOOST)

    assert not isinstance(exc_info.value, ValloxConnectionError)
    assert events == []


@pytest.mark.asyncio
async def test_set_timed_profile_duration_read_failure_writes_nothing(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.holding[20545] = 15
    mock_modbus_unit.fail_read(20545, ModbusTimeoutError("timeout"))
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxConnectionError) as exc_info:
        await device.async_set_profile(Profile.FIREPLACE)

    assert not isinstance(exc_info.value, ValloxPartialWriteError)
    assert isinstance(exc_info.value.__cause__, ModbusTimeoutError)
    assert events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "duration", "failed", "completed"),
    [
        (Profile.HOME, None, 4613, (4609, 4612)),
        (Profile.AWAY, None, 4609, ()),
        (Profile.BOOST, 30, 21766, (4612,)),
        (Profile.FIREPLACE, 15, 4614, (4613, 21767, 4612)),
        (Profile.EXTRA, 65535, 4613, (4614, 4612)),
    ],
)
async def test_set_profile_stops_at_failed_write(
    mock_modbus_unit,
    profile: Profile,
    duration: int | None,
    failed: int,
    completed: tuple[int, ...],
) -> None:
    error = IllegalDataValueError()
    mock_modbus_unit.fail_write(failed, error)
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxPartialWriteError) as exc_info:
        await device.async_set_profile(profile, duration)

    assert isinstance(exc_info.value, ValloxConnectionError)
    assert exc_info.value.__cause__ is error
    assert exc_info.value.completed == completed
    assert exc_info.value.failed == failed
    assert "partially applied" in str(exc_info.value)
    assert tuple(event.address for event in events) == completed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "duration"),
    [
        (Profile.BOOST, 0),
        (Profile.BOOST, -1),
        (Profile.FIREPLACE, 65536),
        (Profile.EXTRA, 1.5),
        (Profile.BOOST, True),
        (Profile.BOOST, "30"),
        (Profile.HOME, 30),
        (Profile.AWAY, 65535),
        (Profile.AUTOMATIC, 1),
        (BasicProfile.HOME, None),
        (3, 30),
        ("BOOST", None),
    ],
)
async def test_set_profile_rejects_invalid_input(
    mock_modbus_unit, profile: object, duration: object
) -> None:
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxInvalidInputError) as exc_info:
        await device.async_set_profile(profile, duration)

    assert isinstance(exc_info.value, ValueError)
    assert events == []
    assert mock_modbus_unit.read_events == []


@pytest.mark.asyncio
async def test_set_profile_reports_missing_configured_duration_register(
    mock_modbus_unit,
) -> None:
    mock_modbus_unit.fail_read(20496, IllegalDataAddressError())
    events = _capture_writes(mock_modbus_unit)
    device = ValloxDevice(mock_modbus_unit)

    with pytest.raises(ValloxConnectionError):
        await device.async_set_profile(Profile.EXTRA)

    assert events == []
