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
| Timer switches | `21766`, `21767`, `21772` | ⚠️ `21766` and `21767` off and on, `21772` only on |
| Filter change date | `20546..20548` | ✅ |

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
| Request retries | 1 second timeout, 500 ms between requests, each timed-out request resent up to 5 times | ✅ |

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
- The filter change date registers `20546..20548` hold day, month and the
  year as `YY` of `20YY`.

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
- Boost also has a timer function On/Off on the panel. With the timer function
  Off while Boost runs, `21766` reads `0`, the unit sets the Boost timer `4612`
  to `65535` (no time limit), Boost stays active and
  `remaining_profile_duration` is `None`. Fireplace behaves the same: with its
  timer function Off while it runs, `21767` reads `0` and `4613` reads
  `65535`.
- Changing from Boost to Fireplace on the panel set the Boost timer `4612` to
  `0`.
- While Extra (programmable mode) runs, the panel keeps showing the previous
  basic mode with the programmable input symbol, as the MyVallox Control manual
  describes.
- Extra cannot be selected on the panel. Even while Extra runs, the panel
  settings offer no timer function for it, unlike Boost and Custom mode, so
  `21772` can only be switched over Modbus.
- While defrosting was active, Boost selected on the panel did not start. How
  the unit handles a Boost started over Modbus during defrosting is not yet
  known.

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
- The library therefore resends each timed-out request, at first up to
  3 times with a 5 second timeout; see "Request Retries" in the README.
  Retries are logged at debug level, so a poor line stays visible.
- With the retries, about a quarter of all requests still needed a second
  attempt and nearly every readings poll had at least one timeout; no request
  failed after its retries. Each timeout adds 5 seconds, so a poll then takes
  11 to 22 seconds instead of about 1 second.
- Replacing the CH340-based USB RS485 adapter with an FTDI FT232R-based adapter
  with built-in termination did not change this pattern.
- Almost every retry succeeded on the second attempt; with independent losses
  at this rate, about one retry in four would have failed again. The timeouts
  therefore depend on timing rather than on line noise. The cause is not yet
  known; the library already keeps 150 ms between requests
  (`VALLOX_MESSAGE_SPACING`), more than the 30 ms the earlier pymodbus YAML
  setup waited.
- A raw traffic log (`tmodbus.raw_traffic`) over 10 minutes showed that the
  unit sends no byte at all for a timed-out request; no late, partial or
  corrupted response arrived and no traffic from another master was seen.
  Answered requests got their response after 11 to 12 ms. 17 of about 71
  requests timed out and every retry 150 ms later was answered. The timer
  switch reads `21766` and `21772` timed out in 10 of 18 polls, `4353` in 3 of
  9 and `4609` in none.
- With `VALLOX_MESSAGE_SPACING` raised to 500 ms in a temporary test, 10 of
  about 71 requests timed out instead of 17 and 3 of 9 readings polls had no
  timeout. The timeouts moved from `21766` and `21772` (1 of 18) to `4389`
  (4 of 9), which twice also timed out on its retry after 5.5 seconds of
  silence. A longer gap between requests therefore does not prevent the
  timeouts; the unit appears not to answer during phases that do not depend
  on the request timing.
- With the timeout also lowered to 1 second in a temporary test, 7 of about
  71 requests timed out on the first attempt and 5 of 9 readings polls had no
  timeout. No response arrived later than 1 second. 3 of 10 retries timed out
  again, but every request was answered by its third attempt, about 3 seconds
  after the first. The longest readings poll took 7.7 seconds instead of up to
  19.7 seconds.
- With 1 second timeout, 500 ms spacing and 5 retries in a temporary test,
  four profile changes (Boost, Home, Fireplace, Home) wrote 16 timer and basic
  profile registers with FC06. Every write response arrived after 11 to 13 ms;
  2 writes timed out once and succeeded on the second attempt. Overall 5 of
  60 requests timed out on the first attempt and all succeeded on the second.
  Two FC06 writes of the Home fan speed `20507` were answered after 10 to
  15 ms and read back with the written value.
- The library therefore uses a 1 second timeout (`VALLOX_TIMEOUT`), 500 ms
  between requests (`VALLOX_MESSAGE_SPACING`) and up to 5 resends
  (`VALLOX_REQUEST_RETRIES`).

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

- [ ] Timer switch `21772` reads off when the Extra timer function is off.
  The panel cannot switch it, so this needs the timer switch write below.

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

Boost during defrosting:

- [ ] While defrosting is active, `await device.async_set_profile(Profile.BOOST)`;
  record whether `4612` keeps the configured duration or returns to `0`,
  whether the fan speeds change and whether Boost starts after defrosting
  ends.

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

### 2026-11-26: Timer functions, filter change date and request retries

Observed through the Home Assistant integration and the MyVallox Control
panel:

- Boost was started on the panel; `remaining_profile_duration` showed the
  configured Boost duration of 15 minutes.
- After the Boost timer function was set Off on the panel, the fan preset and
  `profile` stayed Boost and `remaining_profile_duration` changed to `None`.
- The integration diagnostics then showed `21766` = `0`, `4612` = `65535`,
  `4609` = `0` (Home), `4613` and `4614` = `0` and the fan speed at the Boost
  fan speed of 90 %. The unit itself had replaced the remaining Boost time
  with `65535`.

Fireplace timer function, changed on the panel from Boost to Fireplace and
then with the Fireplace timer function set Off:

- `profile` was Fireplace and `remaining_profile_duration` was `None`.
- The integration diagnostics showed `21767` = `0`, `4613` = `65535`,
  `4612` = `0`, `4614` = `0`, `4609` = `0` (Home), `21766` still `0` and the
  fan speed at the Custom mode fan setting of 50 %.
- After both timer functions were set On again and Boost was started on the
  panel, `remaining_profile_duration` showed the remaining minutes again.
  `async_set_profile(Profile.HOME)` from the integration then ended Boost.
- `async_set_profile(Profile.EXTRA)` from the integration started Extra; the
  panel showed the programmable input symbol and `remaining_profile_duration`
  showed the remaining minutes. The panel settings offered no Extra timer
  function.

Request retries, with debug logging for `vallox_modbus.retry` during about
1.5 hours of Home Assistant operation and repeated profile changes between
Home, Boost and Fireplace; evaluated on a 40-minute log excerpt:

- About 74 timed-out requests out of an estimated 300 were resent; 73
  succeeded on the second attempt and one on the third. None reached the
  fourth attempt.
- 5 of them were writes during profile changes (`4612`, `4613`, `4614`, `4609`);
  all profile changes completed without `ValloxPartialWriteError`.
- Only 5 of about 38 readings polls had no timeout, but every readings and
  settings poll succeeded, so no entity became unavailable.

Filter change date, from the first diagnostics:

- `20546..20548` read `20`, `2`, `25`; the panel showed 20.02.2025 as the last
  filter change.
- With the filter change interval `20537` of 180 days the next filter change
  is 2025-08-19; remaining filter days `4620` read `0`.
