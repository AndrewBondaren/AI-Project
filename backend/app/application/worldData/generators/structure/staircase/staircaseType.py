"""Re-export staircase type contract from dataModel."""

from app.dataModel.structure.enums.staircaseType import (
    StaircaseType,
    StaircaseTypeSpec,
    default_shaft_size_type,
    no_shaft_types,
    requires_shaft,
)

__all__ = [
    "StaircaseType",
    "StaircaseTypeSpec",
    "default_shaft_size_type",
    "no_shaft_types",
    "requires_shaft",
]
