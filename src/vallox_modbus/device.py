"""Top-level Vallox Modbus device object."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any, Final

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
)
from modbus_connection.model import Component, Device, UpdateReport

from .configuration import ValloxConfiguration
from .enums import BasicProfile, Profile, SystemMode
from .exceptions import (
    ValloxConnectionError,
    ValloxError,
    ValloxInvalidInputError,
    ValloxPartialWriteError,
)
from .inputs import ValloxInputs
from .measurements import ValloxMeasurements
from .runtime import ValloxRuntime
from .sensors import ValloxSensors
from .settings import ValloxSettings
from .timer_switches import ValloxTimerSwitches
from .validators import MAX_DURATION, MIN_DURATION, duration_minutes

VALLOX_TIMEOUT: Final = 5.0
VALLOX_CONNECT_DELAY: Final = 0.5
VALLOX_MESSAGE_SPACING: Final = 0.15

NO_TIME_LIMIT: Final = 65535

_BASIC_PROFILES: Final = {
    Profile.HOME: BasicProfile.HOME,
    Profile.AWAY: BasicProfile.AWAY,
    Profile.AUTOMATIC: BasicProfile.AUTOMATIC,
}
_PROFILES_BY_BASIC: Final = {
    basic: profile for profile, basic in _BASIC_PROFILES.items()
}
_TIMER_FIELDS: Final = {
    Profile.BOOST: "boost_timer",
    Profile.FIREPLACE: "fireplace_timer",
    Profile.EXTRA: "extra_timer",
}
_TIMER_SWITCH_FIELDS: Final = {
    Profile.BOOST: "boost_timer_enabled",
    Profile.FIREPLACE: "fireplace_timer_enabled",
    Profile.EXTRA: "extra_timer_enabled",
}
# Highest priority first, as documented in the Vallox Modbus manual.
_TIMED_PROFILE_PRIORITY: Final = (Profile.EXTRA, Profile.FIREPLACE, Profile.BOOST)


def _require_profile(profile: Any) -> Profile:
    """Reject values that are not a Profile, including plain integers."""

    if isinstance(profile, Profile):
        return profile
    raise ValloxInvalidInputError(f"profile must be a Profile, not {profile!r}")


class ValloxDevice(Device):
    """Vallox MV device model."""

    configuration: ValloxConfiguration
    inputs: ValloxInputs
    measurements: ValloxMeasurements
    runtime: ValloxRuntime
    sensors: ValloxSensors
    settings: ValloxSettings
    timer_switches: ValloxTimerSwitches

    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        unit.require_timeout(VALLOX_TIMEOUT)
        unit.require_connect_delay(VALLOX_CONNECT_DELAY)
        unit.set_message_spacing(VALLOX_MESSAGE_SPACING)
        self.configuration = ValloxConfiguration(unit)
        self.inputs = ValloxInputs(unit)
        self.measurements = ValloxMeasurements(unit)
        self.runtime = ValloxRuntime(unit)
        self.sensors = ValloxSensors(unit)
        self.settings = ValloxSettings(unit)
        self.timer_switches = ValloxTimerSwitches(unit)
        self._profile_lock = asyncio.Lock()

    @classmethod
    async def async_probe(cls, unit: ModbusUnit) -> ValloxDevice:
        """Validate that a Modbus unit plausibly serves Vallox MV registers."""

        device = cls(unit)
        try:
            report = await device.async_poll(("measurements", "runtime"))
        except ModbusError as err:
            raise ValloxConnectionError(str(err)) from err

        if not report.complete:
            error = next(iter(report.failed.values()))
            raise ValloxConnectionError(str(error)) from error

        device._validate_probe_values()
        return device

    def _validate_probe_values(self) -> None:
        """Check a small set of live values for conservative plausibility."""

        fan_speed = self.measurements.fan_speed
        if fan_speed is None or not 0 <= fan_speed <= 100:
            msg = f"fan speed is not plausible: {fan_speed!r}"
            raise ValloxError(msg)

        temperatures = (
            self.measurements.extract_air_temperature,
            self.measurements.exhaust_air_temperature,
            self.measurements.outdoor_air_temperature,
            self.measurements.supply_cell_air_temperature,
            self.measurements.supply_air_temperature,
        )
        for temperature in temperatures:
            if temperature is None or not -50.0 <= temperature <= 100.0:
                msg = f"temperature is not plausible: {temperature!r}"
                raise ValloxError(msg)

        if self.runtime.basic_profile is None:
            msg = "basic profile is not plausible"
            raise ValloxError(msg)

        if self.runtime.system_mode is None:
            msg = "system mode is not plausible"
            raise ValloxError(msg)

    async def _async_poll_with_retry(
        self, names: Iterable[str], report: UpdateReport | None = None
    ) -> UpdateReport:
        """Poll like ``async_poll()``, but read a timed-out component once more.

        A component whose read raises ``ModbusTimeoutError`` is read again
        once; only a second timeout counts. Otherwise the semantics of
        ``async_poll()`` apply: ``ModbusConnectionError`` propagates at once,
        ``ModbusTimeoutError`` propagates only while nothing has answered yet,
        every other ``ModbusError`` lands in ``failed``, and listeners fire
        after all reads.
        """

        await self.async_ensure_setup()
        if report is None:
            report = UpdateReport()
        updated: list[str] = []
        for name in names:
            component = getattr(self, name)
            if component is None:
                continue
            try:
                try:
                    await component.async_update(notify=False)
                except ModbusTimeoutError:
                    await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError as err:
                if not report.updated and not report.failed:
                    raise
                report.failed[name] = err
            except ModbusError as err:
                report.failed[name] = err
            else:
                report.updated.add(name)
                updated.append(name)
        for name in updated:
            getattr(self, name).notify()
        return report

    async def async_update_readings(self) -> UpdateReport:
        """Update frequently changing measurement and runtime readings.

        A component that times out is read once more before it is reported.
        """

        return await self._async_poll_with_retry(
            ("measurements", "runtime", "inputs", "sensors", "timer_switches")
        )

    async def async_update_settings(
        self, report: UpdateReport | None = None
    ) -> UpdateReport:
        """Update configured profile settings.

        A component that times out is read once more before it is reported.
        """

        return await self._async_poll_with_retry(("settings", "configuration"), report)

    async def async_update(self) -> UpdateReport:
        """Update readings and settings in one report."""

        report = await self.async_update_readings()
        return await self.async_update_settings(report)

    @property
    def profile(self) -> Profile | None:
        """Effective profile derived from the runtime timers and basic profile.

        A timed profile is active while its timer is not 0; 65535 means active
        without time limit. If several are active, the documented priority is
        Extra (programmable) > Fireplace > Boost > basic profile. Returns None
        if a required value is unavailable.
        """

        for profile in _TIMED_PROFILE_PRIORITY:
            timer = getattr(self.runtime, _TIMER_FIELDS[profile])
            if timer is None:
                return None
            if timer != 0:
                return profile
        basic_profile = self.runtime.basic_profile
        if basic_profile is None:
            return None
        return _PROFILES_BY_BASIC[basic_profile]

    def get_remaining_profile_duration(self, profile: Profile) -> int | None:
        """Remaining minutes of a timed profile.

        Returns None for a profile without a timer, for an unavailable timer,
        for timer value 65535 (no time limit), and for a running timer whose
        timer switch is off, because such a timer does not count down. Raises
        ``ValloxInvalidInputError`` if ``profile`` is not a ``Profile``.
        """

        profile = _require_profile(profile)
        timer_field = _TIMER_FIELDS.get(profile)
        if timer_field is None:
            return None
        timer = getattr(self.runtime, timer_field)
        if timer is None or timer == NO_TIME_LIMIT:
            return None
        enabled = getattr(self.timer_switches, _TIMER_SWITCH_FIELDS[profile])
        if timer != 0 and enabled is False:
            return None
        return timer

    @property
    def remaining_profile_duration(self) -> int | None:
        """Remaining minutes of the effective profile, if it has a time limit."""

        profile = self.profile
        if profile is None:
            return None
        return self.get_remaining_profile_duration(profile)

    @property
    def next_filter_change_date(self) -> date | None:
        """Last filter change date plus the configured filter change interval."""

        changed = self.settings.filter_change_date
        interval = self.configuration.filter_change_interval
        if changed is None or interval is None:
            return None
        return changed + timedelta(days=interval)

    async def _async_write(self, component: Component, field: str, value: Any) -> None:
        """Write one field and translate validation and communication errors."""

        try:
            await component.write(field, value)
        except ModbusError as err:
            raise ValloxConnectionError(str(err)) from err
        except (TypeError, ValueError) as err:
            raise ValloxInvalidInputError(str(err)) from err

    async def _async_read_configured_duration(self, profile: Profile) -> int:
        """Read the configured duration of a timed profile from the device."""

        reader: Component
        if profile is Profile.BOOST:
            reader, field = ValloxSettings(self.modbus_unit), "boost_duration"
        elif profile is Profile.FIREPLACE:
            reader, field = ValloxSettings(self.modbus_unit), "fireplace_duration"
        else:
            reader, field = ValloxConfiguration(self.modbus_unit), "extra_duration"
        reader.restrict_fields((field,))
        try:
            await reader.async_update(notify=False)
        except ModbusError as err:
            raise ValloxConnectionError(str(err)) from err
        value = getattr(reader, field)
        if value is None or not MIN_DURATION <= value <= MAX_DURATION:
            msg = f"configured {field} is not plausible: {value!r}"
            raise ValloxError(msg)
        return value

    async def _async_write_sequence(
        self, writes: list[tuple[Component, str, Any]]
    ) -> None:
        """Write pre-validated fields in order and stop at the first failure."""

        completed: list[int] = []
        for component, field, value in writes:
            address = component.resolved_fields[field].address
            try:
                await component.write(field, value)
            except ModbusError as err:
                msg = (
                    f"writing register {address} failed after writing registers "
                    f"{completed}; the profile change may be partially applied: {err}"
                )
                raise ValloxPartialWriteError(
                    msg, completed=tuple(completed), failed=address
                ) from err
            completed.append(address)

    async def async_set_profile(
        self, profile: Profile, duration: int | None = None
    ) -> None:
        """Change the effective profile with a coordinated write sequence.

        Home, Away and Automatic write the basic profile register 4609 and then
        set the Boost, Fireplace and Extra timers 4612..4614 to 0. Automatic
        (4609 = 2) is not documented in the Vallox Modbus manual (which lists
        0..1 only) and has not been validated on hardware.

        Boost, Fireplace and Extra first write the target timer, then, for an
        explicit ``duration`` other than 65535, set the profile's timer switch
        to on, and finally set the competing timers to 0. ``duration`` is in
        minutes (1..65535, 65535 = no time limit). Without ``duration`` the
        configured duration (20544 Boost, 20545 Fireplace, 20496 Extra) is read
        from the device and the timer switch is left unchanged, so the timer
        only counts down if its switch is already on. ``duration`` is rejected
        for Home, Away and Automatic.

        The writes are not atomic and other Modbus masters or user interfaces
        can change the state in between. Raises ``ValloxInvalidInputError``
        before writing anything for invalid input, ``ValloxConnectionError``
        if the configured duration cannot be read, and
        ``ValloxPartialWriteError`` if a write fails; earlier writes of the
        sequence may already be applied.
        """

        profile = _require_profile(profile)
        if duration is not None:
            if profile in _BASIC_PROFILES:
                msg = f"duration is not supported for {profile.name} profile"
                raise ValloxInvalidInputError(msg)
            try:
                duration = duration_minutes(duration)
            except (TypeError, ValueError) as err:
                raise ValloxInvalidInputError(f"invalid duration: {err}") from err

        async with self._profile_lock:
            runtime = self.runtime
            basic_profile = _BASIC_PROFILES.get(profile)
            if basic_profile is not None:
                writes: list[tuple[Component, str, Any]] = [
                    (runtime, "basic_profile", basic_profile),
                    *((runtime, field, 0) for field in _TIMER_FIELDS.values()),
                ]
            else:
                timer = duration
                if timer is None:
                    timer = await self._async_read_configured_duration(profile)
                writes = [(runtime, _TIMER_FIELDS[profile], timer)]
                if duration is not None and duration != NO_TIME_LIMIT:
                    writes.append(
                        (self.timer_switches, _TIMER_SWITCH_FIELDS[profile], True)
                    )
                writes.extend(
                    (runtime, field, 0)
                    for other, field in _TIMER_FIELDS.items()
                    if other is not profile
                )
            await self._async_write_sequence(writes)

    async def async_set_power(self, on: bool) -> None:
        """Set normal operation on or off."""

        await self._async_write(
            self.runtime,
            "system_mode",
            SystemMode.NORMAL if on else SystemMode.OFF,
        )

    async def async_set_basic_profile(self, profile: BasicProfile) -> None:
        """Set the basic Home/Away/Automatic profile.

        Automatic (4609 = 2) is not documented in the Vallox Modbus manual,
        which lists 0..1 only, and has not been validated on hardware.
        """

        await self._async_write(self.runtime, "basic_profile", profile)

    async def async_set_boost_timer(self, minutes: int) -> None:
        """Set the current Boost timer in minutes."""

        await self._async_write(self.runtime, "boost_timer", minutes)

    async def async_set_fireplace_timer(self, minutes: int) -> None:
        """Set the current Fireplace timer in minutes."""

        await self._async_write(self.runtime, "fireplace_timer", minutes)

    async def async_set_extra_timer(self, minutes: int) -> None:
        """Set the current Extra timer in minutes."""

        await self._async_write(self.runtime, "extra_timer", minutes)

    async def async_set_away_fan_speed(self, percent: int) -> None:
        """Set the configured Away fan speed."""

        await self._async_write(self.settings, "away_fan_speed", percent)

    async def async_set_home_fan_speed(self, percent: int) -> None:
        """Set the configured Home fan speed."""

        await self._async_write(self.settings, "home_fan_speed", percent)

    async def async_set_boost_fan_speed(self, percent: int) -> None:
        """Set the configured Boost fan speed."""

        await self._async_write(self.settings, "boost_fan_speed", percent)

    async def async_set_away_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Away supply air temperature target."""

        await self._async_write(self.settings, "away_air_temperature_target", celsius)

    async def async_set_home_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Home supply air temperature target."""

        await self._async_write(self.settings, "home_air_temperature_target", celsius)

    async def async_set_boost_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Boost supply air temperature target."""

        await self._async_write(self.settings, "boost_air_temperature_target", celsius)

    async def async_set_boost_duration(self, minutes: int) -> None:
        """Set the configured Boost duration."""

        await self._async_write(self.settings, "boost_duration", minutes)

    async def async_set_fireplace_duration(self, minutes: int) -> None:
        """Set the configured Fireplace duration."""

        await self._async_write(self.settings, "fireplace_duration", minutes)

    async def async_set_extra_air_temperature_target(self, celsius: float) -> None:
        """Set the configured Extra supply air temperature target."""

        await self._async_write(
            self.configuration, "extra_air_temperature_target", celsius
        )

    async def async_set_extra_extract_fan(self, percent: int) -> None:
        """Set the configured Extra extract fan speed."""

        await self._async_write(self.configuration, "extra_extract_fan", percent)

    async def async_set_extra_supply_fan(self, percent: int) -> None:
        """Set the configured Extra supply fan speed."""

        await self._async_write(self.configuration, "extra_supply_fan", percent)

    async def async_set_extra_duration(self, minutes: int) -> None:
        """Set the configured Extra duration."""

        await self._async_write(self.configuration, "extra_duration", minutes)

    async def async_set_bypass_locked(self, locked: bool) -> None:
        """Set whether heat recovery cell bypass is locked."""

        await self._async_write(self.configuration, "bypass_locked", locked)
