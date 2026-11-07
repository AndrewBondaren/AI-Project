"""Admission checks for Open Water source schemas and diagnostic records."""
from pydantic import ValidationError

from app.application.worldData.generators.hydrology.encoding import sourceBindings, sourceLocks, sourceShape
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry
from app.dataModel.planning.diagnostics.planDiagnostic import (
    PlanDiagnostic, PlanDiagnosticDisposition, require_concrete_diagnostic,
)
from app.encoding.canonicalCodec import CanonicalCodec, CanonicalEncodingError


def require_source_schema_v1() -> None:
    """Refuse lock drift before encoding/fingerprinting; no registry mutation."""
    try:
        manifest = sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1
        if type(manifest) is not CanonicalSchemaManifest or type(getattr(manifest, "entries", None)) is not tuple:
            raise CanonicalEncodingError("source binding drift: expected manifest with tuple entries")
        if any(type(entry) is not RegisteredTypeEntry for entry in manifest.entries):
            raise CanonicalEncodingError("source binding drift: expected RegisteredTypeEntry instances")
        try:
            CanonicalSchemaManifest.model_validate(manifest, strict=True)
        except ValidationError as exc:
            raise CanonicalEncodingError(f"source binding drift: {exc}") from exc
        bindings = tuple((e.type_id, e.python_type, e.kind) for e in manifest.entries)
        if bindings != sourceBindings.SOURCE_BINDINGS:
            raise CanonicalEncodingError("open-water source v1 ID binding drift")
        shapes, aliases = sourceShape.source_snapshot()
        if set(shapes) != {owner for _, owner, _ in sourceBindings.SOURCE_BINDINGS}:
            raise CanonicalEncodingError("open-water source v1 closure drift")
        for identity, owner, _ in sourceBindings.SOURCE_BINDINGS:
            if shapes[owner] != sourceLocks.SHAPE_LOCK[identity]:
                raise CanonicalEncodingError(f"open-water source v1 shape drift: {identity}")
        if aliases != sourceLocks.ALIAS_LOCK:
            raise CanonicalEncodingError("open-water source v1 alias drift")
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc


def require_source_diagnostics_v1(diagnostics: tuple[PlanDiagnostic, ...]) -> None:
    require_source_schema_v1()
    if type(diagnostics) is not tuple:
        raise CanonicalEncodingError("source diagnostics must be an immutable tuple")
    try:
        codec = CanonicalCodec(sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1)
        for diagnostic in diagnostics:
            carrier = type(diagnostic)
            if carrier not in sourceBindings.DIAGNOSTIC_FACTS or type(diagnostic.issue) is not sourceBindings.DIAGNOSTIC_FACTS[carrier]:
                raise CanonicalEncodingError("unadmitted source diagnostic carrier or fact")
            if carrier is PlanDiagnostic and diagnostic.disposition is not PlanDiagnosticDisposition.FALLBACK:
                raise CanonicalEncodingError("water kind mismatch requires fallback")
            checked = require_concrete_diagnostic(diagnostic)
            # Pydantic can normalize a StrEnum to a string even in strict mode.
            if codec.encode(checked) != codec.encode(diagnostic):
                raise CanonicalEncodingError("source diagnostic changed wire type during validation")
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc
