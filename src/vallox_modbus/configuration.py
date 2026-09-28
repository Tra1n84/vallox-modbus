"""Vallox device configuration registers."""

from __future__ import annotations

from modbus_connection.model import Component, boolean, enum, gauge, integer

from .enums import HeaterType, HeatRecoveryCellType, ModbusParity
from .validators import (
    air_temperature_target,
    boolean_value,
    duration_minutes,
    percent,
)


class ValloxConfiguration(Component):
    """Vallox device and installation configuration from holding registers."""

    register_space = "holding"
    register_ranges = (
        (20482, 20488),
        (20493, 20496),
        (20537, 20540),
        (20552, 20552),
    )

    modbus_address = integer(20482, signed=False)
    modbus_baud_x100 = integer(20483, signed=False)
    modbus_frame = integer(20484, signed=False)
    extract_fan_balance_base = integer(20485, signed=False, unit="%")
    supply_fan_balance_base = integer(20486, signed=False, unit="%")
    fireplace_extract_fan = integer(20487, signed=False, unit="%")
    fireplace_supply_fan = integer(20488, signed=False, unit="%")
    extra_air_temperature_target = gauge(
        20493,
        0.01,
        offset=-273.15,
        signed=False,
        writable=air_temperature_target,
        unit="°C",
    )
    extra_extract_fan = integer(20494, signed=False, writable=percent, unit="%")
    extra_supply_fan = integer(20495, signed=False, writable=percent, unit="%")
    extra_duration = integer(20496, signed=False, writable=duration_minutes, unit="min")
    filter_change_interval = integer(20537, signed=False, unit="days")
    heat_recovery_cell_type = enum(20538, HeatRecoveryCellType)
    extra_heater_type = enum(20539, HeaterType)
    post_heater_type = enum(20540, HeaterType)
    bypass_locked = boolean(20552, writable=boolean_value)

    @property
    def modbus_baudrate(self) -> int | None:
        """Configured Modbus baudrate in baud."""

        if self.modbus_baud_x100 is None:
            return None
        return self.modbus_baud_x100 * 100

    @property
    def modbus_parity(self) -> ModbusParity | None:
        """Configured Modbus parity decoded from the frame register."""

        if self.modbus_frame is None:
            return None
        try:
            return ModbusParity(self.modbus_frame >> 8)
        except ValueError:
            return None

    @property
    def modbus_stop_bits(self) -> int | None:
        """Configured Modbus stop bits decoded from the frame register."""

        if self.modbus_frame is None:
            return None
        stop_bits = self.modbus_frame & 0xFF
        if stop_bits in {1, 2}:
            return stop_bits
        return None
