# Vallox Backend Compatibility Assessment

Assessed on 2026-11-05 against the Home Assistant Core `dev` Vallox
integration, the upstream WebSocket library, and the current local
`vallox-modbus` implementation. Upstream links are moving references; recheck
them before implementation. This is a design assessment, not a compatibility
guarantee or a completed adapter.

## Integration Contract

The current Core integration uses more than a client with matching method
names. It expects a metric data object, WebSocket-specific profile enums and
exceptions, device metadata, and profile operations with particular side
effects. A class named `Vallox` alone would not satisfy that contract.

| Existing contract | Current Modbus equivalent | Work remaining |
| --- | --- | --- |
| `fetch_metric_data()` | `async_update()` returns an update report; values live on components | Build a normalized data snapshot after polling, with explicit treatment of failed components. |
| `MetricData.get(key, default)` | Typed component attributes | Map the metric keys used by Core; preserve unknown/unavailable values. |
| `MetricData.profile` | `runtime.basic_profile` and three runtime timers | Derive the effective profile; establish timer precedence for Modbus. |
| `get_fan_speed(profile)` | Away/Home/Boost speed settings | Explicit enum mapping; reject profiles without a single configurable speed. |
| `get_remaining_profile_duration(profile)` | Boost/Fireplace/Extra runtime timers | Map active timers without confusing configured duration with remaining time. |
| `set_profile(profile, duration)` | Basic-profile setter and separate timer setters | Implement coordinated profile changes, timer resets, default-duration handling and failure semantics. |
| `set_fan_speed(profile, percent)` | Three semantic profile speed setters | Dispatch by profile and normalize validation errors. |
| `set_values(mapping)` | Power, temperature-target and bypass setters | Translate only supported named operations; reject unknown keys before writing. No arbitrary register access. |
| `set_filter_change_date(date)` | No equivalent currently modeled | Verify documented registers and write behavior before exposing the date entity. |
| `ValloxApiException` / invalid-input errors | Probe-only Vallox exceptions; other operations expose dependency/validation errors | Agree a shared error contract and translate at the backend boundary. |
| `uuid`, `model`, `sw_version` | No device identity component currently modeled | Research documented metadata; agree stable identity and duplicate-device policy. |

## Entity Coverage

| Core feature | Available in this library | Compatibility limitation |
| --- | --- | --- |
| Power | System mode and power setter | Hardware off/on is confirmed in the current local validation notes. |
| Home/Away presets | Basic profile read/write | Switching presets must also handle active timed overrides. |
| Auto preset | `BasicProfile.AUTOMATIC` read/write | Already implemented, but hardware validation remains open. |
| Boost/Fireplace/Extra presets | Runtime timers and configured durations | Individual timer writes are validated; a complete profile-transition operation is not. |
| Fan percentage / profile speed attributes | Current fan speed and three profile settings | Core fan percentage uses the configured profile speed; the separate speed sensor uses live fan speed. Preserve this distinction. |
| Five main air temperatures, humidity, CO2, fan RPM | Measurement component | Preserve units and unavailable values. |
| Optional temperature | Sensor component | Existing low-value/no-sensor ambiguity remains; do not invent a sentinel. |
| Heat exchanger state | Runtime component | Translate enum explicitly. |
| Three temperature target numbers | Settings and semantic setters | Read/write paths already implemented and hardware-validated. |
| Bypass lock switch | Configuration and setter | Hardware validation remains open. |
| Active-profile duration sensor | Three runtime timers | Requires effective-profile mapping. |
| Filter due timestamp / last-change date | Remaining days and change interval only | Remaining days are not the original last-change date or an exact due timestamp. |
| Post-heater binary sensor | Not currently modeled | Heater type is not heater activity. Research a documented activity register. |
| Extract efficiency sensor | Not currently modeled | Research documented data or formula; do not invent a calculation. |
| Device registry identity and configuration URL | No verified equivalent identity yet | A Modbus gateway host is not necessarily the device web interface. Do not fabricate a UUID or URL. |

## Profile Semantics

The WebSocket library's profile enum is numerically different from the Modbus
basic-profile enum. Values must be translated by meaning, never by a direct
integer cast.

The WebSocket implementation selects an effective profile from timers before
the basic state. Its setter clears competing timers and obtains a configured
duration when no duration is supplied. These are requirements to investigate
for compatible behavior, not evidence that Modbus supports identical atomic
operations or timer priority.

Before adding a high-level Modbus profile operation:

- Verify documented timer priority, cancellation and indefinite-duration
  behavior, including the meaning of `65535` on each runtime timer.
- Verify transitions while another timed profile is active.
- Define ordering and partial-write behavior. Several Modbus writes must not
  be presented as atomic unless that behavior is verified.
- Serialize a multi-request transition at the appropriate boundary and
  refresh state after success or partial failure. Account for polling and
  external controllers; a local lock cannot exclude another physical master.
- Read a configured default duration when required; do not silently rely on
  uninitialized or stale settings.

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
2. Add a documented effective-profile model and coordinated profile operation
   after resolving the protocol questions above; retain existing low-level
   semantic setters.
3. Define consistent communication and validation errors for the public
   operations consumed by the adapter, including partial update reports.
4. Investigate identity, filter dates, heater activity and efficiency in the
   Vallox documentation. Add only verified support, or expose an explicit
   capability limitation in the integration design.
5. Test mapping and profile transitions, including enum differences,
   unavailable data, failures after an earlier successful write and unchanged
   WebSocket behavior in the Core integration tests.

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
