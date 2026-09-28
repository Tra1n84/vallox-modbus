"""Exceptions for the Vallox Modbus device library."""


class ValloxError(Exception):
    """Base Vallox Modbus error."""


class ValloxConnectionError(ValloxError):
    """Vallox Modbus communication error."""
