# vallox-modbus

`vallox-modbus` is a Python library for reading and controlling Vallox MV
ventilation units through the Home Assistant `modbus-connection` architecture.

## Status

The core read model and the main documented control writes are implemented.

Write support is intentionally scoped to semantic operations for profile
selection, power, profile fan speeds, temperature targets, timers/durations,
Extra profile settings, and bypass lock. Bypass-lock writes, the coordinated
`async_set_profile()` sequence for Home, Away and the timed profiles, and timer
switch writes still need hardware validation. Broad Vallox MV model
compatibility has not yet been validated.

Hardware communication has been tested against one Vallox ValloPlus 510 MV
installation over Modbus RTU with unit ID 1, 19200 baud, 8 data bits, even
parity and 1 stop bit. Other Vallox MV models and firmware versions still need
validation.

## Installation

```bash
pip install vallox-modbus
```

For a serial transport, for example to run the diagnostic script from a source
checkout, install the optional `serial` extra:

```bash
pip install "vallox-modbus[serial]"
```

## Architecture

The library models the Vallox register map and expects the caller to provide a
`modbus_connection.ModbusUnit`. It does not create or own the physical Modbus
connection.

```text
Home Assistant
        |
        | provides Modbus unit
        v
vallox-modbus
        |
        v
modbus-connection
        |
        v
Serial RTU / TCP / other supported transport
```

Vallox MV units use holding registers directly. This library does not apply a
global `-1` or `+1` address offset.

## Supported Data

Measurement registers `4353..4364`:

- current fan speed
- extract, exhaust, outdoor, supply cell, and supply air temperatures
- RH and CO2 levels
- extract and supply fan RPM
- humidity
- CO2

Input registers `4365..4370`:

- fireplace switch
- digital input
- analog control input
- raw multisensor values

Runtime registers `4609..4621`:

- basic profile: Home, Away, or Automatic
- system mode
- defrosting state
- Boost, Fireplace, and Extra runtime timers
- weekly timer enabled
- heat exchanger state
- total and current uptime
- filter remaining
- fault / limp state

Optional sensor registers:

- internal humidity sensor
- RH sensors 0..5
- CO2 sensors 0..5
- optional temperature sensor
- VOC level and VOC sensors 0..3

Settings registers:

- Away, Home, and Boost RH/CO2 control flags
- Away, Home, and Boost fan speed settings
- Away, Home, and Boost supply air temperature targets
- configured Boost and Fireplace durations
- last filter change date (`20546..20548`, year read as `2000 + YY`)

Timer switch registers `21766..21767` and `21772`:

- Boost, Fireplace, and Extra timer enabled switches

Derived values on `ValloxDevice`:

- `profile`: effective `Profile` (Home, Away, Automatic, Boost, Fireplace, or
  Extra). A timed profile is active while its timer is not `0`; `65535` means
  active without time limit. The documented priority is Extra (programmable) >
  Fireplace > Boost > basic profile.
- `remaining_profile_duration` and `get_remaining_profile_duration(profile)`:
  remaining minutes, or `None` for profiles without a timer, timer value
  `65535`, and running timers whose timer switch is off.
- `next_filter_change_date`: last filter change date plus the configured
  filter change interval.

Configuration registers:

- Modbus address, baudrate, parity, and stop bits
- fan balance base settings
- fireplace and Extra profile fan settings
- Extra profile supply air temperature target and duration
- filter change interval
- heat recovery cell and heater types

Writable registers:

- power on/off through documented system mode values
- coordinated profile change with `async_set_profile()`
- Home/Away/Automatic basic profile
- current Boost, Fireplace, and Extra timers
- Away, Home, and Boost fan speed settings
- Away, Home, and Boost supply air temperature targets
- configured Boost, Fireplace, and Extra durations
- Extra profile fan and supply air temperature settings
- heat recovery cell bypass lock

Filter change date writes are not supported.

## Profile Changes

`async_set_profile(profile, duration=None)` writes a sequence of registers:

| Profile | Writes, in order |
| --- | --- |
| Home / Away / Automatic | `4609` = `0` / `1` / `2`, then `4612`, `4613`, `4614` = `0` |
| Boost | `4612` = duration, [`21766` = `1`], `4613` = `0`, `4614` = `0` |
| Fireplace | `4613` = duration, [`21767` = `1`], `4612` = `0`, `4614` = `0` |
| Extra | `4614` = duration, [`21772` = `1`], `4612` = `0`, `4613` = `0` |

- `duration` is in minutes, `1..65535`; `65535` means no time limit. It is
  rejected for Home, Away, and Automatic.
- The timer switch in brackets is written only for an explicit `duration`
  other than `65535`, as in the manual's example.
- Without `duration`, the configured duration (`20544` Boost, `20545`
  Fireplace, `20496` Extra) is read from the device before writing, and the
  timer switch is left unchanged. If that switch is off, the profile stays
  active without counting down.
- The target timer is written first, so the unit does not fall back to the
  basic profile between writes. The timer switch follows, so the requested
  profile is complete before competing timers are cleared.
- Automatic (`4609` = `2`) is documented in the Vallox Modbus manual and is
  hardware-validated.

The writes are not atomic. Other Modbus masters and the unit's own user
interfaces can change the state in between; the library only serializes its own
profile changes. Invalid input raises `ValloxInvalidInputError` before anything
is written. A failure while reading the configured duration raises
`ValloxConnectionError` before anything is written. A failed write raises
`ValloxPartialWriteError` (a `ValloxConnectionError`); earlier writes may
already be applied, `completed` lists the acknowledged register addresses, and
`failed` names the register whose write failed and may or may not have been
applied. Refresh the readings after any error.

## Errors

All public `async_set_*` methods and `async_set_profile()` raise
`ValloxInvalidInputError` for invalid values and `ValloxConnectionError` for
Modbus communication errors, with the original `modbus_connection` error as
the cause. `ValloxInvalidInputError` is also a `ValueError`.

## Polling Model

`ValloxDevice.async_probe()` validates a `modbus_connection.ModbusUnit` for
setup flows by reading only the measurements and runtime register groups and
checking a small set of live values for plausibility. It performs no writes.

`async_update_readings()` updates frequently changing values from the
measurements, runtime, inputs, sensors, and timer switch components. Timer
switches are read with the readings because the Vallox digital input can change
them.

`async_update_settings()` updates slower changing values from the settings and
configuration components.

`async_update()` runs both groups and returns one combined update report.

Both groups read a component once more if its read times out, so a single
lost response does not fail it. Only a second timeout counts. As with
`Device.async_poll()`, a timeout then raises `ModbusTimeoutError` while nothing
in the poll has answered yet, and is recorded in the report's `failed`
otherwise. Other Modbus errors are not retried.

Write methods are exposed as explicit semantic operations on `ValloxDevice`,
such as `async_set_power()`, `async_set_profile()`,
`async_set_basic_profile()`,
`async_set_home_fan_speed()`, and
`async_set_home_air_temperature_target()`. The library does not expose a
generic arbitrary register write API.

## Example

```python
from vallox_modbus import Profile, ValloxDevice

device = await ValloxDevice.async_probe(unit)
await device.async_update_readings()

print(device.measurements.outdoor_air_temperature)
print(device.measurements.humidity)
print(device.runtime.basic_profile)
print(device.runtime.heat_exchanger_state)
print(device.profile)
print(device.remaining_profile_duration)

await device.async_update_settings()
print(device.settings.home_fan_speed)
print(device.configuration.modbus_baudrate)
print(device.sensors.rh_sensors)
print(device.next_filter_change_date)

await device.async_set_profile(Profile.BOOST, 30)
```

## Diagnostic Query

The diagnostic script is an application and may create a physical serial
connection. The reusable package code does not.

```bash
uv run --extra serial python script/query.py \
  /dev/serial/by-id/usb-1a86_USB2.0-Ser_-if00-port0 \
  --unit 1 \
  --baudrate 19200 \
  --parity E \
  --stopbits 1
```

Defaults are unit `1`, baudrate `19200`, bytesize `8`, parity `E`, and stopbits
`1`. Pass `--details` to print optional input and sensor readings. Pass
`--settings` to read and print the settings and configuration components as
well.

## References

- Vallox manual search:
  <https://www.vallox.com/en/support-and-instructions/manual-search/>
- Home Assistant Modbus developer documentation:
  <https://developers.home-assistant.io/docs/modbus/introduction/>
- `modbus-connection`:
  <https://home-assistant-libs.github.io/modbus-connection/>
