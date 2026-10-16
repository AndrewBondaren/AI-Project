"""Bundle domain errors — WB-3 (no FastAPI in application)."""

from __future__ import annotations


class BundleValidationError(Exception):
    """Invalid bundle shape, level, or section payload."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
