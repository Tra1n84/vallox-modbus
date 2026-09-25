# Home Assistant Core Plan

## Goal

Extend the existing Home Assistant Core `vallox` integration with a Modbus
backend instead of creating a second official integration.

The user-facing setup should remain one integration:

```text
Vallox
```

During setup, the user should choose the connection type:

- MyVallox API / WebSocket
- Modbus

The Modbus contribution should aim for feature parity with the existing
websocket backend's core fan and configuration entities. That means write
support must be implemented and validated in `vallox-modbus` before proposing
the Home Assistant Core change.

The Core proposal can still be split into reviewable steps, but the direction
presented to maintainers should not be a permanently read-only Modbus backend.

## Current Core Integration Shape

Current upstream path:

```text
homeassistant/components/vallox
```

Observed files:

- `__init__.py`
- `config_flow.py`
- `coordinator.py`
- `entity.py`
- `fan.py`
- `sensor.py`
- `binary_sensor.py`
- `number.py`
- `switch.py`
- `date.py`
- `manifest.json`
- `strings.json`

Current backend:

- Requirement: `vallox-websocket-api`
- Client: `vallox_websocket_api.Vallox`
- Config flow input: `host`
- Coordinator data: websocket API metric data
- Poll interval: `STATE_SCAN_INTERVAL = timedelta(seconds=60)`
- Existing platforms include fan, sensors, binary sensors, numbers, switches,
  and dates.

## Desired Architecture

Keep the Home Assistant integration transport-aware, but keep protocol modeling
inside external libraries.

```text
homeassistant.components.vallox
        |
        | selects backend from config entry
        v
Vallox websocket backend     Vallox Modbus backend
vallox-websocket-api         vallox-modbus
                              |
                              v
                          modbus-connection
```

The Modbus backend should receive a `modbus_connection.ModbusUnit` from Home
Assistant's Modbus infrastructure. It must not create its own serial or TCP
connection inside reusable library code.

## Config Flow Proposal

Add a first setup step:

```text
connection_type
```

Possible values:

- `websocket`
- `modbus`

WebSocket path:

- Preserve existing behavior.
- Ask for host/IP.
- Validate by calling the current websocket client.

Modbus path:

- Prefer using Home Assistant's current Modbus connection architecture.
- Ask for the existing Modbus hub/unit configuration in the style expected by
  the current Home Assistant Modbus APIs.
- Validate by reading a small safe register group, probably readings
  `4353..4364`.

Reconfigure path:

- For websocket entries: continue to reconfigure host.
- For Modbus entries: reconfigure only values actually stored in the config
  entry. Do not duplicate physical connection settings if Home Assistant owns
  them elsewhere.

## Coordinator Proposal

The current integration has one `ValloxDataUpdateCoordinator` whose data type is
websocket metric data. Modbus will likely need either:

- a shared abstract adapter with a normalized data object, or
- separate coordinators and entity classes per backend.

Prefer a normalized adapter first, if it does not distort either backend.

Sketch:

```python
class ValloxBackend(Protocol):
    async def async_update_readings(self) -> ValloxReadingData: ...
    async def async_update_settings(self) -> ValloxSettingsData: ...
```

For the initial Modbus PR, it may be simpler to add a Modbus-specific
coordinator and branch entity setup based on `connection_type`.

Polling and writes:

- Readings: every 60 seconds, matching the existing integration.
- Settings/configuration: less frequent, e.g. 5-15 minutes, or on demand.
- Fan/control writes should be included once validated in `vallox-modbus`, so
  the Modbus backend can support the existing fan and number entity model.

## Write Support Roadmap

The existing websocket backend exposes writable Home Assistant entities. A
Modbus backend that stays permanently read-only would not be feature-equivalent.

Implement Modbus writes in this library before opening the Core PR. Each write
path should be covered by unit tests and hardware validation notes before being
used from Home Assistant Core.

Current `vallox-modbus` status:

- explicit semantic write methods exist for power, Home/Away profile, timers,
  profile fan speeds, profile temperature targets, Extra settings, and bypass
  lock
- writes are unit-tested against exact Modbus register addresses and encoded
  raw values
- most core writes have been hardware-validated on one Vallox ValloPlus 510 MV:
  - Home/Away profile changes
  - Boost, Fireplace, and Extra timers
  - Away/Home/Boost fan speed settings
  - Away/Home/Boost supply air temperature targets
  - Boost, Fireplace, and Extra configured durations
  - Extra fan and temperature settings
- power on/off and bypass lock writes still need hardware validation before
  being used from Home Assistant Core

Suggested Core readiness sequence:

1. Finish remaining hardware validation:
   - power on/off via documented system mode register
   - bypass lock
2. Map validated HA fan/number parity writes:
   - Home/Away profile changes
   - Home/Away/Boost fan speed settings
   - Home/Away/Boost supply air temperature targets
3. Map validated timer/action writes where they fit the existing Core entity
   model:
   - Boost timer
   - Fireplace timer
   - Extra timer
4. Keep maintenance writes out until documented and validated:
   - filter reset only after documentation and hardware behavior are verified

Do not add write support for registers whose semantics are unclear. Write APIs
should be narrow, named after protocol semantics, and avoid generic arbitrary
register writes.

## Entity Mapping V1

Map stable read-only Modbus data and validated core control writes first.

Enabled by default:

- `measurements.fan_speed` -> sensor, `%`
- `measurements.extract_air_temperature` -> sensor, temperature
- `measurements.exhaust_air_temperature` -> sensor, temperature
- `measurements.outdoor_air_temperature` -> sensor, temperature
- `measurements.supply_cell_air_temperature` -> sensor, temperature
- `measurements.supply_air_temperature` -> sensor, temperature
- `measurements.humidity` -> sensor, humidity
- `measurements.co2` -> sensor, CO2, disabled if unavailable/no sensor
- `runtime.basic_profile` -> sensor or fan preset source
- `runtime.system_mode` -> sensor/diagnostic
- `runtime.defrosting` -> binary sensor
- `runtime.fault` -> binary sensor, problem class
- `runtime.heat_exchanger_state` -> sensor
- `runtime.filter_remaining` -> sensor, days

Disabled by default / diagnostic:

- extract/supply RPM
- RH/CO2/VOC per-sensor values
- raw multisensor values
- Modbus configuration registers
- fan balance base
- heater/cell type
- configured durations
- profile speed settings

Fan entity:

- The Modbus backend should expose the fan entity once the library supports the
  same core fan controls as the websocket backend:
  - on/off
  - Home/Away preset selection, and additional profiles only when protocol
    behavior is verified
  - percentage writes through documented profile speed settings

Numbers/switches:

- Expose number entities for the same temperature targets as the websocket
  backend after write support is validated in `vallox-modbus`.
- Keep risky or poorly documented switch/action entities out of the first Core
  PR even if lower-level library methods exist.

## Dependency / Manifest Impact

Add the external library as a Home Assistant requirement only when the Core PR is
ready:

```json
"requirements": [
  "vallox-websocket-api==...",
  "vallox-modbus==..."
]
```

The `modbus-connection` dependency should remain transitive through
`vallox-modbus`, unless Home Assistant requires explicit dependency declaration.

The integration remains:

```json
"domain": "vallox",
"integration_type": "device",
"iot_class": "local_polling"
```

## Tests Needed In Home Assistant Core

Config flow:

- websocket path keeps existing behavior
- modbus path creates config entry
- validation failure is reported as `cannot_connect`
- duplicate handling remains correct per connection type
- reconfigure works for both paths

Coordinator:

- websocket coordinator remains unchanged
- modbus readings update succeeds
- modbus update failure becomes `UpdateFailed`
- settings/configuration polling does not block normal readings

Entities:

- sensors expose correct native values and units
- unavailable Modbus values become `None`
- binary sensors map booleans correctly
- entity unique IDs remain stable
- device info works without websocket-only fields such as websocket UUID/model,
  unless equivalent Modbus metadata is available

## Owner Proposal Summary

When approaching the current Core code owners, present this as a feature-parity
proposal:

- keep the existing `vallox` domain
- preserve the current websocket backend
- add Modbus as a second backend
- implement and hardware-test Modbus writes in `vallox-modbus` before Core use
- include the core fan and number write paths in the Core design
- defer only risky or poorly documented actions

The request should not frame Modbus as permanently read-only. It should frame
read-only work as the foundation we already completed in the library, with most
core writes already implemented, unit-tested, and hardware-validated. The
remaining library validation items before Core use are power on/off and bypass
lock writes.

## Open Questions

- How should Home Assistant expose a shared Modbus unit to an integration in the
  current Core API?
- Should Modbus entries store a Modbus hub reference, unit ID, or both?
- Can the existing `vallox` entity descriptions be reused with a backend value
  accessor, or is a Modbus-specific entity set clearer?
- Which Modbus fan controls are required in the first Core PR for acceptable
  parity with the current websocket fan entity?
- Is there documented device metadata over Modbus that can provide stable model
  or serial identifiers?

## Out Of Scope For First Core PR

- Separate `vallox_modbus` Home Assistant integration/domain
- HACS-only custom integration as the end goal
- Arbitrary Modbus writes
- Poorly documented or unvalidated profile/action writes
- Any Boost, Fireplace, or Extra behavior beyond the validated timer writes
- Weekly schedule management
- Clock/time writes
- Filter reset

The first Core PR should include only writes that have been implemented,
unit-tested, and hardware-tested in `vallox-modbus`.
