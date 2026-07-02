"""REF-W cross-reference index — import-only, after ``facade`` normalize."""

from app.application.jsonValidation.index.build import build_world_registry_index
from app.application.jsonValidation.index.refKinds import RefKind
from app.application.jsonValidation.index.validate import validate_ref_w
from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex

__all__ = [
    "RefKind",
    "WorldRegistryIndex",
    "build_world_registry_index",
    "validate_ref_w",
]
