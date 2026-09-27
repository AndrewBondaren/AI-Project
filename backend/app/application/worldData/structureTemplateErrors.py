"""Domain errors for structure template library / import — map to HTTP only in routes."""

from __future__ import annotations


class StructureTemplateError(Exception):
    """Base structure-template domain error."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class StructureTemplateNotFoundError(StructureTemplateError):
    """Missing template or FS path."""


class StructureTemplateValidationError(StructureTemplateError):
    """Invalid structure JSON, stem mismatch, duplicate uid in stdlib, etc."""
