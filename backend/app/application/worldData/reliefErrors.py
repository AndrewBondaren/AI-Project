"""Domain errors for relief library / import — map to HTTP only in routes (RELIEF-T-3)."""

from __future__ import annotations


class ReliefError(Exception):
    """Base relief domain error."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ReliefNotFoundError(ReliefError):
    """Missing template or FS path."""


class ReliefValidationError(ReliefError):
    """Invalid outline, R29 stem mismatch, structure_refs, etc."""
