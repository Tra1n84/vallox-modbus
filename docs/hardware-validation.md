# Hardware Validation

This file records hardware behavior that has been validated against a real
Vallox installation. It intentionally avoids installation-specific paths,
addresses, and private Home Assistant details.

## Scope

All validation ran against one Vallox ValloPlus 510 MV installation over
Modbus RTU. Broader Vallox MV model and firmware compatibility still needs
validation.

Connection settings:

- Unit ID: 1
- Baudrate: 19200
- Data bits: 8
- Parity: even
- Stop bits: 1

## Summary

Status: ✅ validated on hardware · ⚠️ not or only partly validated on hardware
· ⛔ not implemented

Details of each validation run are in the [History](#history).

### Reads

| Area | Methods and registers | Status |
| --- | --- | --- |
| Read paths | `async_update_readings()`<br>`async_update_settings()`<br>`script/query.py --details --settings` | ✅ |
| Read groups | measurements, runtime, inputs, optional sensors, settings, configuration | ✅ |
| Timer switches | `21766`, `21767`, `21772` | ⚠️ `21767` off and on, `21766` and `21772` only on |
| Filter change date | `20546..20548` | ⚠️ not validated |

### Writes

| Area | Methods | Status |
| --- | --- | --- |
| Profile fan speeds | `async_set_home_fan_speed()`<br>`async_set_away_fan_speed()`<br>`async_set_boost_fan_speed()` | ✅ |
| Supply air temperature targets | `async_set_home_air_temperature_target()`<br>`async_set_away_air_temperature_target()`<br>`async_set_boost_air_temperature_target()`<br>`async_set_extra_air_temperature_target()` | ✅ |
| Profile durations | `async_set_boost_duration()`<br>`async_set_fireplace_duration()`<br>`async_set_extra_duration()` | ✅ Fireplace with FC16 |
| Extra profile fans | `async_set_extra_extract_fan()`<br>`async_set_extra_supply_fan()` | ✅ |
| Current timers | `async_set_boost_timer()`<br>`async_set_fireplace_timer()`<br>`async_set_extra_timer()` | ✅ |
| Basic profile | `async_set_basic_profile()` Home, Away, Automatic | ✅ |
| Power | `async_set_power()` | ✅ |
| Profile without duration | `async_set_profile(profile)` for every profile | ✅ |
| Profile with duration | `async_set_profile(profile, duration)`, also `65535` | ⚠️ not validated |
| Timer switch writes | `21766`, `21767`, `21772` (FC06), used by `async_set_profile()` with a duration | ⚠️ not validated |
| Bypass lock | `async_set_bypass_locked()` | ⚠️ not validated |
| Filter change date | `20546..20548` | ⛔ no library API |

### Communication

| Area | Behavior | Status |
| --- | --- | --- |
| Request retries | each timed-out request resent up to 3 times | ⚠️ not validated |

## Known Behavior

Observations that explain how the library decodes and writes values.

Reads:

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

Writes:

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

Profiles and the MyVallox Control panel:

- The MyVallox Control panel calls the Fireplace profile Custom mode.
- The panel has no separate timer switch. The first screen of the Custom mode
  settings (Info, then the pen icon) is the timer function On/Off;
  `remaining_profile_duration`, which reads register `21767`, follows it.
- With the timer function Off, `async_set_profile(Profile.FIREPLACE)` without
  a duration activates Fireplace and `remaining_profile_duration` is `None`.
  With the timer function On, `remaining_profile_duration` shows the configured
  Fireplace duration (`20545`).
- While Extra (programmable mode) runs, the panel keeps showing the previous
  basic mode with the programmable input symbol, as the MyVallox Control manual
  describes.

Communication:

- In continuous Home Assistant operation, single requests regularly got no
  response and failed with `Response timeout after 5.0 seconds`. All register
  areas were affected, for example `read_holding_registers(4389, 6)`,
  `(20493, 4)`, `(20505, 4)`, `(20511, 4)`, and `(21772, 1)`, as well as
  `write_register(4612, 0)` during a Boost -> Away profile change, which then
  raised `ValloxPartialWriteError`.
- Even with one component-level retry, such failures occurred 8 times in 30
  minutes.
- The earlier Home Assistant YAML Modbus setup used pymodbus with 3 retries per
  request, which hid these timeouts; `modbus-connection` sends every request
  once.
- The library therefore resends each timed-out request up to 3 times; see
  "Request Retries" in the README. Retries are logged at debug level, so a poor
  line stays visible.

Vallox Modbus manual note:

- The register table of the Modbus manual D5269 describes `4613` as the
  configured Custom timer time and `20545` as the decreasing current value.
  The manual's introduction and its example "Activating the Custom mode for 15
  minutes" use `4613` as the counting-down timer instead. The library follows
  the introduction, which matches the profile changes in the
  [History](#history). The table makes the same swap for Boost (`4612`,
  `20544`) and Programmable (`4614`, `20496`).

## Validation Checklist

Open steps only; completed steps are listed in the [History](#history). Run
only against an installation where changing the profile is acceptable, note
the initial state first, and restore it afterwards. Refresh with
`await device.async_update()` after each step and compare the unit's own user
interface.

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

- [ ] Timer switches `21766` and `21772` read off when the Boost and Extra
  timer functions are off.
- [ ] Filter change date matches the user interface, including whether the
  year register holds `YY` of `20YY`.

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
- [ ] `await device.async_set_profile(Profile.BOOST, 65535)`; profile stays
  active, `remaining_profile_duration` is `None`.
- [ ] With Fireplace active, `await device.async_set_profile(Profile.BOOST, 2)`;
  the unit changes to Boost without showing the basic profile in between.
- [ ] Record whether FC06 writes to `21766`, `21767`, and `21772` succeed.
  FC06 timed out on `20545` during earlier validation.

Request retries:

- [ ] Enable debug logging for `vallox_modbus.retry` and run the Home Assistant
  integration for at least 30 minutes; note how many retries are logged.
- [ ] No settings or configuration entities become unavailable because of a
  single timed-out request.
- [ ] Repeat Boost -> Away profile changes; none raises
  `ValloxPartialWriteError` unless the log shows 4 timed-out attempts.

Filter change date write (diagnostic only, no library API):

- [ ] Note the current values of `20546..20548`.
- [ ] Write a test date with a raw diagnostic call, for example
  `await unit.write_registers(20546, [day, month, year - 2000])`, and confirm
  it in the user interface. Record whether FC16 and FC06 are accepted.
- [ ] Check whether the write also changes `4620` remaining filter days.
- [ ] Restore the noted values.

## History

Completed validation runs, oldest first.

### 2026-09-25: Initial validation

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

Home/Away basic profile, normal system mode, fault state, defrost state, fan
speed, temperatures, humidity, fan RPM, heat exchanger state, filter remaining,
and timers decoded plausibly. The other read observations are listed in
[Known Behavior](#known-behavior).

Validated write paths:

- `async_set_home_fan_speed(60)`
- `async_set_away_fan_speed(30)`
- `async_set_boost_fan_speed(90)`
- `async_set_away_air_temperature_target(15.0)`
- `async_set_home_air_temperature_target(13.0)`
- `async_set_boost_air_temperature_target(15.0)`
- `async_set_boost_duration(30)`
- `async_set_fireplace_duration(15)`, with FC16
- `async_set_extra_duration(10)`
- `async_set_extra_air_temperature_target(15.0)`
- `async_set_extra_extract_fan(50)`
- `async_set_extra_supply_fan(50)`
- `async_set_basic_profile()` by switching Away -> Home -> Away
- `async_set_boost_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_fireplace_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_extra_timer()` by setting the current timer 0 -> 1 -> 0

### Recorded 2026-11-22: Power

- `async_set_power()` by switching normal operation off -> on; see
  [Known Behavior](#known-behavior).

### Recorded 2026-11-23: Automatic profile and request timeouts

- Automatic basic profile (`4609` = `2`) was observed on this installation and
  shown as Automatic by the unit's user interface.
- `async_set_basic_profile(BasicProfile.AUTOMATIC)`; `4609` reads `2` and the
  user interface shows Automatic.
- `async_set_profile(Profile.AUTOMATIC)`; `4609` reads `2`, timers
  `4612..4614` read `0`.
- Restored with `async_set_profile(Profile.HOME)` or `AWAY`.
- The request timeouts in continuous Home Assistant operation, see
  [Known Behavior](#known-behavior), led to the per-request retries.

### 2026-11-24: Profile changes

Validated with the fan presets of the Home Assistant integration, which call
`async_set_profile(profile)` without a duration. Each change was confirmed on
the unit and its MyVallox Control panel:

- Home and Away: switching between them works.
- Boost: ran for its configured duration of 15 minutes, showed the remaining
  time and returned to the previous basic profile.
- Fireplace: ran for its configured duration of 60 minutes, showed the
  remaining time and returned to the previous basic profile.
- Automatic: works, as validated earlier.
- Changes between the timed profiles Boost, Fireplace and Extra: the unit
  changed to the selected timed profile.
- Selecting Home or Away while Boost or Fireplace was active ended the timed
  profile.
- Extra (programmable mode), started without a digital input: with the Extra
  supply and extract fan settings at 70 %, the fans sped up from about 1500 and
  1800 rpm to about 1800 and 2000 rpm. The panel kept showing the previous
  basic mode (At Home) with the programmable input symbol. Extra ran for its
  configured duration and returned to the previous basic profile; selecting At
  Home also ended it.
- No write errors were reported.
- While Boost and Extra ran, `remaining_profile_duration` showed the remaining
  time, so the timer switches `21766` and `21772` were read as on. Their off
  state was not observed.
- `async_update_readings()` reported `timer_switches` as updated; the Home
  Assistant profile duration sensor, which needs it, had values.

Fireplace profile and timer switch, observed through the Home Assistant
integration:

- The Custom mode supply and extract fan settings were 50 % and selecting
  Custom mode on the panel made `profile` read Fireplace.
- `remaining_profile_duration`, which reads register `21767`, followed the
  panel's timer function On/Off.
- With the timer function Off, `async_set_profile(Profile.FIREPLACE)` without
  a duration activated Fireplace and `remaining_profile_duration` was `None`.
  The same held after activating Custom mode on the panel.
- After the timer function was set On on the panel,
  `async_set_profile(Profile.FIREPLACE)` without a duration activated Fireplace
  and `remaining_profile_duration` showed the configured Fireplace duration
  (`20545`).

The register values were not read directly; the observations come from the
integration's state and the unit's user interface.
