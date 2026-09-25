#!/usr/bin/env python3
"""Query a Vallox MV unit once over Modbus RTU."""

from __future__ import annotations

import argparse
import asyncio
from enum import IntEnum

from modbus_connection import ModbusError, ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection

from vallox_modbus import ValloxDevice


def _enum_label(value: IntEnum | None) -> str:
    if value is None:
        return "unavailable"
    return value.name.replace("_", " ").title()


def _value(value: object, unit: str = "") -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return str(value)
    if unit:
        return f"{value} {unit}"
    return str(value)


def _temperature(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.1f} °C"


def _print_row(label: str, value: str) -> None:
    print(f"{label + ':':28} {value}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query a Vallox MV Modbus RTU unit.")
    parser.add_argument("device", help="Serial device path, for example /dev/ttyUSB0")
    parser.add_argument("--unit", type=int, default=1, help="Modbus unit id")
    parser.add_argument("--baudrate", type=int, default=19200)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--parity", default="E", choices=("N", "E", "O", "n", "e", "o"))
    parser.add_argument("--stopbits", type=int, default=1, choices=(1, 2))
    parser.add_argument("--settings", action="store_true", help="Also read settings")
    return parser.parse_args()


async def _async_main() -> int:
    args = _parse_args()
    connection = ModbusConnection(
        ModbusSerialParams(
            device=args.device,
            framer="rtu",
            baudrate=args.baudrate,
            bytesize=args.bytesize,
            parity=args.parity.upper(),
            stopbits=args.stopbits,
        )
    )

    try:
        device = ValloxDevice(connection.for_unit(args.unit))
        report = await device.async_update_readings()
        if args.settings:
            report = await device.async_update_settings(report)
    except ModbusError as err:
        print("Vallox Modbus")
        print()
        print(f"Connection failed: {err}")
        return 1
    finally:
        await connection.close()

    measurements = device.measurements
    runtime = device.runtime

    print("Vallox Modbus")
    print()
    if not report.complete:
        print("Connection incomplete")
        for name, err in sorted(report.failed.items()):
            print(f"{name}: {err}")
        return 1

    print("Connection OK")
    print()
    _print_row("Basic profile", _enum_label(runtime.basic_profile))
    _print_row("System mode", _enum_label(runtime.system_mode))
    _print_row("Fault", _value(runtime.fault))
    _print_row("Defrosting", _value(runtime.defrosting))
    print()
    _print_row("Fan speed", _value(measurements.fan_speed, "%"))
    print()
    _print_row(
        "Extract air temperature",
        _temperature(measurements.extract_air_temperature),
    )
    _print_row(
        "Exhaust air temperature",
        _temperature(measurements.exhaust_air_temperature),
    )
    _print_row(
        "Outdoor air temperature",
        _temperature(measurements.outdoor_air_temperature),
    )
    _print_row(
        "Supply cell temperature",
        _temperature(measurements.supply_cell_air_temperature),
    )
    _print_row(
        "Supply air temperature",
        _temperature(measurements.supply_air_temperature),
    )
    print()
    _print_row("Humidity", _value(measurements.humidity, "%"))
    _print_row("CO2", _value(measurements.co2, "ppm"))
    print()
    _print_row("RH level", _enum_label(measurements.rh_level))
    _print_row("CO2 level", _enum_label(measurements.co2_level))
    print()
    _print_row("Extract fan", _value(measurements.extract_fan_rpm, "RPM"))
    _print_row("Supply fan", _value(measurements.supply_fan_rpm, "RPM"))
    print()
    _print_row("Heat exchanger", _enum_label(runtime.heat_exchanger_state))
    _print_row("Filter remaining", _value(runtime.filter_remaining, "days"))
    print()
    _print_row("Boost remaining", _value(runtime.boost_timer, "min"))
    _print_row("Fireplace remaining", _value(runtime.fireplace_timer, "min"))
    _print_row("Extra remaining", _value(runtime.extra_timer, "min"))
    if args.settings:
        settings = device.settings
        print()
        _print_row("Away speed setting", _value(settings.away_fan_speed, "%"))
        _print_row("Home speed setting", _value(settings.home_fan_speed, "%"))
        _print_row("Boost speed setting", _value(settings.boost_fan_speed, "%"))
        _print_row(
            "Away temperature target",
            _temperature(settings.away_air_temperature_target),
        )
        _print_row(
            "Home temperature target",
            _temperature(settings.home_air_temperature_target),
        )
        _print_row(
            "Boost temperature target",
            _temperature(settings.boost_air_temperature_target),
        )
        _print_row("Boost duration setting", _value(settings.boost_duration, "min"))
        _print_row(
            "Fireplace duration setting",
            _value(settings.fireplace_duration, "min"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_async_main()))
