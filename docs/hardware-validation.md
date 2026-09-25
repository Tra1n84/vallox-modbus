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
- `async_set_boost_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_fireplace_timer()` by setting the current timer 0 -> 1 -> 0
- `async_set_extra_timer()` by setting the current timer 0 -> 1 -> 0

Write behavior notes:

- `async_set_fireplace_duration(15)` timed out when register `20545` was written
  with FC06.
- A direct FC16 write to register `20545` succeeded.
- The library therefore uses FC16 for `fireplace_duration`.
- Runtime timer registers remained distinct from configured duration registers.

Not yet hardware-validated:

- `async_set_power()`
- `async_set_bypass_locked()`

Scope:

- This validates one Vallox ValloPlus 510 MV installation only.
- Broader Vallox MV model and firmware compatibility still needs validation.
