# Vallox Backend Compatibility Assessment

Assessed on 2026-11-05 against the Home Assistant Core `dev` Vallox
integration, the upstream WebSocket library, and the current local
`vallox-modbus` implementation. Upstream links are moving references; recheck
them before implementation. This is a design assessment, not a compatibility
guarantee or a completed adapter.

Updated on 2026-11-22 for `vallox-modbus` 0.2.0, which adds the effective
profile, the coordinated profile change, timer switch reads, filter change date
reads, remaining profile duration, and a uniform write error contract.

## Integration Contract

The current Core integration uses more than a client with matching method
names. It expects a metric data object, WebSocket-specific profile enums and
exceptions, device metadata, and profile operations with particular side
effects. A class named `Vallox` alone would not satisfy that contract.

| Existing contract | Current Modbus equivalent | Work remaining |
| --- | --- | --- |
| `fetch_metric_data()` | `async_update()` returns an update report; values live on components | Build a normalized data snapshot after polling, with explicit treatment of failed components. |
| `MetricData.get(key, default)` | Typed component attributes | Map the metric keys used by Core; preserve unknown/unavailable values. |
| `MetricData.profile` | `ValloxDevice.profile` (`Profile` or `None`) | Translate `Profile` to the WebSocket enum by meaning. Modbus has no `NONE`; unavailable data is `None`. |
| `get_fan_speed(profile)` | Away/Home/Boost speed settings | Explicit enum mapping; reject profiles without a single configurable speed. |
| `get_remaining_profile_duration(profile)` | `ValloxDevice.get_remaining_profile_duration(profile)` and `remaining_profile_duration` | Same `None` semantics as the WebSocket library. Timer switch reads are not hardware-validated. |
| `get_timer_enabled(profile)` | `timer_switches.boost_timer_enabled`, `fireplace_timer_enabled`, `extra_timer_enabled` | Dispatch by profile in the adapter. |
| `set_profile(profile, duration)` | `ValloxDevice.async_set_profile(profile, duration)` | Implemented and unit-tested, not hardware-validated. Not atomic; a failed write raises `ValloxPartialWriteError`. Differences: `duration` must be `1..65535` (WebSocket also accepts `0` for the configured duration; pass `None`), and `duration` is rejected for Home/Away/Automatic (WebSocket ignores it). |
| `set_fan_speed(profile, percent)` | Three semantic profile speed setters | Dispatch by profile and normalize validation errors. |
| `set_values(mapping)` | Power, temperature-target and bypass setters | Translate only supported named operations; reject unknown keys before writing. No arbitrary register access. |
| `filter_change_date`, `next_filter_change_date` | `settings.filter_change_date`, `ValloxDevice.next_filter_change_date` | Read-only. Year is read as `2000 + YY`; invalid stored dates read as `None`. |
| `set_filter_change_date(date)` | Not implemented | Documented registers `20546..20548` are R/W, but write behavior needs hardware validation first. |
| `ValloxApiException` / invalid-input errors | `ValloxError`, `ValloxConnectionError`, `ValloxPartialWriteError`, `ValloxInvalidInputError` (also a `ValueError`) | All public writes translate Modbus errors to `ValloxConnectionError` and validation errors to `ValloxInvalidInputError`. Map these at the backend boundary. |
| `uuid`, `model`, `sw_version` | No device identity component currently modeled | Not in the Vallox Modbus manual; see open items. |

## Entity Coverage

| Core feature | Available in this library | Compatibility limitation |
| --- | --- | --- |
| Power | System mode and power setter | Hardware off/on is confirmed in the current local validation notes. |
| Home/Away presets | `profile` and `async_set_profile()` | The sequence clears active timed profiles; hardware validation of the sequence remains open. |
| Auto preset | `Profile.AUTOMATIC` / `BasicProfile.AUTOMATIC` read/write | Value `2` is documented in the Vallox Modbus manual; read and write validated on hardware. |
| Boost/Fireplace/Extra presets | `profile` and `async_set_profile()` | Individual timer writes are validated; the coordinated sequence and timer switch writes are not. |
| Fan percentage / profile speed attributes | Current fan speed and three profile settings | Core fan percentage uses the configured profile speed; the separate speed sensor uses live fan speed. Preserve this distinction. |
| Five main air temperatures, humidity, CO2, fan RPM | Measurement component | Preserve units and unavailable values. |
| Optional temperature | Sensor component | Existing low-value/no-sensor ambiguity remains; do not invent a sentinel. |
| Heat exchanger state | Runtime component | Translate enum explicitly. |
| Three temperature target numbers | Settings and semantic setters | Read/write paths already implemented and hardware-validated. |
| Bypass lock switch | Configuration and setter | Hardware validation remains open. |
| Active-profile duration sensor | `remaining_profile_duration` | Implemented with WebSocket-compatible semantics. |
| Filter due timestamp / last-change date | `settings.filter_change_date`, `next_filter_change_date` | Read-only; the date entity cannot be written. |
| Post-heater binary sensor | Not currently modeled | Heater type is not heater activity. Research a documented activity register. |
| Extract efficiency sensor | Not currently modeled | Research documented data or formula; do not invent a calculation. |
| Device registry identity and configuration URL | No verified equivalent identity yet | A Modbus gateway host is not necessarily the device web interface. Do not fabricate a UUID or URL. |

## Profile Semantics

The WebSocket library's profile enum is numerically different from the Modbus
basic-profile enum. Values must be translated by meaning, never by a direct
integer cast.

The Vallox Modbus manual documents the behavior the library now implements:

- A timed profile is active while its timer is not `0`; `65535` disables the
  countdown. Priority is Extra (programmable) > Fireplace > Boost > basic
  profile.
- A timer switch that is off stops the countdown but leaves the profile active.
  The digital input can change the timer switches, so they are polled with the
  readings.
- Switching the basic profile optionally clears all timers. The library always
  clears them.

`async_set_profile()` writes the target timer first, then the timer switch for
an explicit duration, then clears the competing timers. It reads the
configured duration from the device when no duration is supplied. The writes
are not atomic; a lock serializes only this library instance's profile changes,
not other Modbus masters or user interfaces. The caller should refresh state
after success or failure. Transitions on hardware remain to be validated; see
the [validation checklist](../docs/hardware-validation.md#validation-checklist).

## Proposed Boundary

Keep `vallox-modbus` transport-neutral and independent of
`vallox-websocket-api`. Register addresses, codecs, validation and documented
device operations belong in this library.

Propose a small backend protocol in the Core integration, with WebSocket and
Modbus adapters. It should cover normalized readings, supported controls,
metadata and errors, allowing entities to share behavior where supported.
The WebSocket adapter should preserve existing behavior and unique IDs.
The Modbus adapter would translate semantic library values and methods, not
register addresses.

Alternatively, maintainers may prefer a compatibility facade supplied by an
external library. Agree its ownership, types and versioning before building
it. Do not add a dependency on the WebSocket package just to reuse its class
name, enums or exceptions without that agreement.

Unsupported entities or actions need explicit capability handling. Returning
`None` alone is insufficient: some existing consumers turn a missing value
into a false state, and device identity is required during entity setup.

## Library Work Before Core Implementation

1. Agree the common contract and adapter location with maintainers.
2. Done in 0.2.0: effective-profile model and coordinated profile operation;
   the low-level semantic setters are retained.
3. Done in 0.2.0: consistent communication and validation errors for all
   public writes. Partial update reports remain `UpdateReport` from
   `modbus-connection`.
4. Done in 0.2.0 for filter dates (read-only). Identity, heater activity and
   efficiency remain open; see below.
5. Hardware-validate the new write paths, then test mapping and profile
   transitions in the integration, including enum differences, unavailable
   data, and failures after an earlier successful write.

## Open Items

- Device identity, model and software version: `A_CYC_UUID0..7` (`8214..8221`),
  `A_CYC_MACHINE_MODEL` (`17`) and `A_CYC_APPL_SW_VERSION_1..9` (`2..10`) are
  WebSocket metric names that do not appear in the Vallox Modbus manual. Model
  them only after a hardware read test.
- Extract efficiency: `A_CYC_EXTRACT_EFFICIENCY` (`32776`) is not in the
  Vallox Modbus manual; hardware read test first.
- Post-heater activity: `A_CYC_IO_HEATER` (`4868`) is not in the Vallox Modbus
  manual; hardware read test first.
- Hardware validation of bypass lock, the `async_set_profile()` sequence, timer
  switch writes, and a filter change date write.
- Filter change date write API, after hardware validation.

No adapter or Home Assistant integration code is implemented by this document.
Full feature parity is not yet established.

## Sources

- [Core coordinator](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/coordinator.py)
- [Core fan](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/fan.py)
- [Core sensors](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/sensor.py)
- [Core binary sensors](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/binary_sensor.py)
- [Core numbers](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/number.py)
- [Core switches](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/switch.py)
- [Core dates](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/date.py)
- [Core entity metadata](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/entity.py)
- [Core services](https://github.com/home-assistant/core/blob/dev/homeassistant/components/vallox/services.py)
- [WebSocket client and metric data](https://github.com/yozik04/vallox_websocket_api/blob/master/vallox_websocket_api/vallox.py)
- [Local hardware validation](../docs/hardware-validation.md)
