# Hardware Validation

This file records hardware behavior that has been validated against a real
Vallox installation. It intentionally avoids installation-specific paths,
addresses, and private Home Assistant details.

## Vallox ValloPlus 510 MV

Validated on 2026-09-25 against one Vallox ValloPlus 510 MV installation over
Modbus RTU.

Connection settings:

- Unit ID: 1
- Baudrate: 19200
- Data bits: 8
- Parity: even
- Stop bits: 1

Validated read paths:

- `async_update_readings()`
- `async_update_settings()`
- `script/query.py --details --settings`

Validated read groups:

- measurements
- runtime
- inputs
- optional sensors
- settings
- configuration

Observed read behavior:

- Home/Away basic profile, normal system mode, fault state, defrost state, fan
  speed, temperatures, humidity, fan RPM, heat exchanger state, filter
  remaining, and timers decoded plausibly.
- Automatic basic profile is documented for register `4609` as value `2`, but
  was not observed on this installation during validation.
- `CO2 level: No Sensor` was observed with raw CO2 value `0`; the library maps
  that CO2 value to unavailable.
- Internal humidity sensor raw value `56` decoded to an impossible negative
  humidity by the documented formula; the library maps out-of-range internal
  humidity values to unavailable.
- RH and CO2 sensor arrays were unavailable on the tested installation.
- VOC sensor values returned `0 ppm`; these were left as reported because the
  documented no-sensor marker for individual VOC sensors is `65535`.
- Optional temperature reported a very low celsius value; this was left as
  reported because no register-specific no-sensor marker was verified.

Validated write paths:

- `async_set_home_fan_speed(60)`
- `async_set_away_fan_speed(30)`
- `async_set_boost_fan_speed(90)`
- `async_set_away_air_temperature_target(15.0)`
- `async_set_home_air_temperature_target(13.0)`
- `async_set_boost_air_temperature_target(15.0)`
- `async_set_boost_duration(30)`
- `async_set_fireplace_duration(15)`
- `async_set_extra_duration(10)`
- `async_set_extra_air_temperature_target(15.0)`
- `async_set_extra_extract_fan(50)`
- `async_set_extra_supply_fan(50)`
- `async_set_basic_profile()` by switching Away -> Home -> Away
- `async_set_power()` by switching normal operation off -> on
- `async_set_boost_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_fireplace_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_extra_timer()` by setting the current timer 0 -> 1 -> 0

Write behavior notes:

- `async_set_fireplace_duration(15)` timed out when register `20545` was written
  with FC06.
- A direct FC16 write to register `20545` succeeded.
- The library therefore uses FC16 for `fireplace_duration`.
- `boost_duration` and `extra_duration` were validated without this FC16
  workaround.
- Runtime timer registers remained distinct from configured duration registers.
- `async_set_power(False)` set system mode to `Off`, fan speed to `0 %`, and
  extract and supply fan speeds to `0 RPM`.
- `async_set_power(True)` restored system mode to `Normal`.

Not yet hardware-validated:

- `async_set_basic_profile(BasicProfile.AUTOMATIC)`; register `4609` is
  documented for `0..1` only
- `async_set_bypass_locked()`
- `async_set_profile()` write sequences for every profile:
  - Home, Away, and Automatic: `4609`, then `4612`, `4613`, `4614` = `0`
  - Boost, Fireplace, and Extra with an explicit duration, with `65535`, and
    with the configured duration read from `20544`, `20545`, or `20496`
  - transitions while another timed profile is active
- Timer switch writes to `21766`, `21767`, and `21772` (FC06), used by
  `async_set_profile()` for an explicit duration. FC06 timed out on `20545`
  during earlier validation, so FC06 acceptance on these registers is open.
- Timer switch reads from `21766..21767` and `21772`
- Filter change date reads from `20546..20548`, including whether the year
  register holds `YY` of `20YY`
- Filter change date writes; the library does not implement them

## Validation Checklist

Not yet executed. Run only against an installation where changing the profile
is acceptable, note the initial state first, and restore it afterwards. Refresh
with `await device.async_update()` after each step and compare the unit's own
user interface.

Setup and reads:

```python
device = ValloxDevice(unit)
await device.async_update()
device.runtime.basic_profile, device.profile, device.remaining_profile_duration
device.timer_switches.boost_timer_enabled
device.timer_switches.fireplace_timer_enabled
device.timer_switches.extra_timer_enabled
device.settings.filter_change_date, device.next_filter_change_date
```

- [ ] Timer switches and filter change date match the user interface.
- [ ] `async_update_readings()` reports `timer_switches` as updated.

Automatic profile:

- [ ] `await device.async_set_basic_profile(BasicProfile.AUTOMATIC)`; `4609`
  reads `2` and the user interface shows Automatic, or the write is rejected.
- [ ] `await device.async_set_profile(Profile.AUTOMATIC)`; same check, timers
  `4612..4614` read `0`.
- [ ] Restore with `await device.async_set_profile(Profile.HOME)` or `AWAY`.

Bypass lock:

- [ ] `await device.async_set_bypass_locked(True)`; `20552` reads `1` and the
  user interface shows the bypass locked.
- [ ] `await device.async_set_bypass_locked(False)`; restore the initial value.

Profile sequence:

- [ ] `await device.async_set_profile(Profile.BOOST, 2)`; profile Boost, timer
  `2`, `21766` reads `1`, timer counts down, unit returns to the basic profile.
- [ ] `await device.async_set_profile(Profile.FIREPLACE, 2)`; same checks with
  `4613` and `21767`.
- [ ] `await device.async_set_profile(Profile.EXTRA, 2)`; same checks with
  `4614` and `21772`.
- [ ] `await device.async_set_profile(Profile.BOOST)`; timer equals the
  configured Boost duration and `21766` is unchanged. Repeat for Fireplace and
  Extra.
- [ ] `await device.async_set_profile(Profile.BOOST, 65535)`; profile stays
  active, `remaining_profile_duration` is `None`.
- [ ] With Fireplace active, `await device.async_set_profile(Profile.BOOST, 2)`;
  the unit changes to Boost without showing the basic profile in between.
- [ ] With a timed profile active, `await device.async_set_profile(Profile.HOME)`
  and `Profile.AWAY`; all timers read `0`.
- [ ] Record whether FC06 writes to `21766`, `21767`, and `21772` succeed.

Filter change date write (diagnostic only, no library API):

- [ ] Note the current values of `20546..20548`.
- [ ] Write a test date with a raw diagnostic call, for example
  `await unit.write_registers(20546, [day, month, year - 2000])`, and confirm
  it in the user interface. Record whether FC16 and FC06 are accepted.
- [ ] Check whether the write also changes `4620` remaining filter days.
- [ ] Restore the noted values.

Scope:

- This validates one Vallox ValloPlus 510 MV installation only.
- Broader Vallox MV model and firmware compatibility still needs validation.
