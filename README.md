# vallox-modbus

`vallox-modbus` is a Python library for reading Vallox MV ventilation units
through the Home Assistant `modbus-connection` architecture.

## Status

Early development. Read-only.

This first version has not been validated against real hardware by this
repository.

## Architecture

The library models the Vallox register map and expects the caller to provide a
`modbus_connection.ModbusUnit`. It does not create or own the physical Modbus
connection.

```text
Application / Home Assistant
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

Runtime registers `4609..4621`:

- basic profile
- system mode
- defrosting state
- Boost, Fireplace, and Extra runtime timers
- weekly timer enabled
- heat exchanger state
- total and current uptime
- filter remaining
- fault / limp state

## Example

```python
from vallox_modbus import ValloxDevice

device = ValloxDevice(unit)
await device.async_update_readings()

print(device.measurements.outdoor_air_temperature)
print(device.measurements.humidity)
print(device.runtime.basic_profile)
print(device.runtime.heat_exchanger_state)
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
`1`.

## References

- Vallox manual search:
  <https://www.vallox.com/en/support-and-instructions/manual-search/>
- Home Assistant Modbus developer documentation:
  <https://developers.home-assistant.io/docs/modbus/introduction/>
- `modbus-connection`:
  <https://home-assistant-libs.github.io/modbus-connection/>
