"""Per-request retry of timed-out Modbus requests."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from modbus_connection import ModbusTimeoutError, ModbusUnit

_LOGGER = logging.getLogger(__name__)


class TimeoutRetryingUnit:
    """Wrap a ``ModbusUnit`` and resend a register or coil request that timed out.

    Only ``ModbusTimeoutError`` is retried, up to ``retries`` times, so one
    request is sent at most ``retries + 1`` times. ``ModbusConnectionError``,
    Modbus exception responses and every other error propagate at once. Each
    retry is logged at debug level.

    Only the raw register and coil requests are retried. All writes the
    Vallox library sends through them set absolute values, so resending a
    write whose response was lost is safe. Every other attribute is delegated
    to the wrapped unit unchanged.
    """

    def __init__(self, unit: ModbusUnit, retries: int) -> None:
        if retries < 0:
            raise ValueError("retries must be non-negative")
        self._unit = unit
        self._retries = retries

    def __getattr__(self, name: str) -> Any:
        return getattr(self._unit, name)

    async def _request[T](
        self, function: str, request: Callable[..., Awaitable[T]], *args: Any
    ) -> T:
        attempts = self._retries + 1
        attempt = 1
        while True:
            try:
                return await request(*args)
            except ModbusTimeoutError as err:
                if attempt >= attempts:
                    raise
                attempt += 1
                _LOGGER.debug(
                    "%s(%s) timed out, retrying (attempt %d of %d): %s",
                    function,
                    ", ".join(repr(arg) for arg in args),
                    attempt,
                    attempts,
                    err,
                )

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        return await self._request(
            "read_holding_registers", self._unit.read_holding_registers, address, count
        )

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        return await self._request(
            "read_input_registers", self._unit.read_input_registers, address, count
        )

    async def write_register(self, address: int, value: int) -> None:
        await self._request("write_register", self._unit.write_register, address, value)

    async def write_registers(self, address: int, values: list[int]) -> None:
        await self._request(
            "write_registers", self._unit.write_registers, address, values
        )

    async def read_coils(self, address: int, count: int) -> list[bool]:
        return await self._request("read_coils", self._unit.read_coils, address, count)

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        return await self._request(
            "read_discrete_inputs", self._unit.read_discrete_inputs, address, count
        )

    async def write_coil(self, address: int, value: bool) -> None:
        await self._request("write_coil", self._unit.write_coil, address, value)

    async def write_coils(self, address: int, values: list[bool]) -> None:
        await self._request("write_coils", self._unit.write_coils, address, values)
