"""Exceptions for the Vallox Modbus device library."""


class ValloxError(Exception):
    """Base Vallox Modbus error."""


class ValloxConnectionError(ValloxError):
    """Vallox Modbus communication error."""


class ValloxInvalidInputError(ValloxError, ValueError):
    """Invalid value passed to a Vallox write operation."""


class ValloxPartialWriteError(ValloxConnectionError):
    """Communication error during a multi-register write sequence.

    The writes of a sequence are not atomic. Registers listed in ``completed``
    were acknowledged by the device. The write to ``failed`` raised an error and
    may or may not have been applied. Later writes in the sequence were not
    attempted. Refresh the device state before relying on it.
    """

    def __init__(
        self,
        message: str,
        *,
        completed: tuple[int, ...],
        failed: int,
    ) -> None:
        super().__init__(message)
        self.completed = completed
        self.failed = failed
