"""Open-water storage v1 bindings and in-process record admission."""
import dataclasses
import typing
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, ValidationError

from app.encoding.canonicalCodec import CanonicalEncodingError
from app.application.worldData.generators.hydrology.encoding import sourceBindings
from app.application.worldData.generators.hydrology.encoding.sourceShape import shape_repr
from app.application.worldData.generators.hydrology.encoding.sourceSchema import (
    require_source_diagnostics_v1, require_source_schema_v1,
)
from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactKind, ArtifactRef, FormatVersion
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.hydrology.pack.root import HydrologyPackRoot, HydrologyShardRef
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.registryKey import RegistryKey


_STORAGE = (
    (60001, HydrologyPackRoot), (60002, HydrologyShardRef), (60003, HydrologyPackShard),
    (60005, ArtifactRef), (60006, ArtifactKind),
)
OPEN_WATER_PACK_SCHEMA_V1 = CanonicalSchemaManifest(entries=tuple(sorted((
    *sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries,
    *(RegisteredTypeEntry(type_id=i, python_type=t,
                          kind=CanonicalTypeKind.ENUM if issubclass(t, Enum) else CanonicalTypeKind.RECORD)
      for i, t in _STORAGE)), key=lambda entry: entry.type_id)))


# Stable ordered TLV field identifiers. V1 binds each identifier to the same POJO name.
_V1_WIRE_FIELDS = {
    60001: ('source_ref', 'dependencies', 'diagnostics', 'topology', 'coverage_region_uid', 'z_min', 'z_max', 'bodies', 'unions', 'source_mapping', 'shards'),
    60002: ('tx', 'ty', 'artifact'),
    60003: ('source_ref', 'tx', 'ty', 'bed', 'wet_runs', 'shore_rows'),
    60005: ('kind', 'format_key', 'format_version', 'content_hash', 'nbytes', 'row_count'),
}


def _shape(owner):
    name = owner.__module__ + "." + owner.__name__
    if issubclass(owner, Enum):
        rows = [(key, getattr(member, "wire_value", member.value)) for key, member in owner.__members__.items()]
    else:
        rows = [(key, shape_repr(field.annotation), repr(field.default), repr(field.default_factory), repr(field.metadata))
                for key, field in owner.model_fields.items()]
    return sha256(repr((name, rows)).encode()).hexdigest()


def _closure(roots):
    pending = list(roots)
    records = set()
    aliases = {}
    while pending:
        owner = pending.pop()
        if owner is PlanDiagnostic[typing.Any]:
            continue  # Source admission binds the concrete diagnostic records.
        if isinstance(owner, (typing.NewType, typing.TypeAliasType)):
            existing = aliases.get(owner.__name__)
            if existing is not None:
                if existing is not owner:
                    raise CanonicalEncodingError(f"storage alias collision: {owner.__name__}")
                continue
            aliases[owner.__name__] = owner
            pending.append(owner.__value__ if isinstance(owner, typing.TypeAliasType) else owner.__supertype__)
        elif isinstance(owner, Enum):
            pending.append(type(owner))
        elif (origin := typing.get_origin(owner)) is not None:
            if origin is not RegistryKey:
                pending.extend(typing.get_args(owner))
                if dataclasses.is_dataclass(origin):
                    pending.append(origin)
        elif isinstance(owner, type) and owner not in records:
            if issubclass(owner, BaseModel):
                records.add(owner)
                pending.extend(f.annotation for f in owner.model_fields.values())
            elif dataclasses.is_dataclass(owner):
                records.add(owner)
                pending.extend(typing.get_type_hints(owner, include_extras=True).values())
            elif issubclass(owner, Enum) and owner.__members__:
                records.add(owner)
    return records, aliases


def require_pack_schema_v1() -> None:
    require_source_schema_v1()
    expected = {e.type_id: (e.python_type, e.kind) for e in sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries}
    for i, owner in _STORAGE:
        if i in expected:
            raise CanonicalEncodingError(f"storage binding collides with source ID: {i}")
        expected[i] = (owner, CanonicalTypeKind.ENUM if issubclass(owner, Enum) else CanonicalTypeKind.RECORD)
        if _shape(owner) != _STORAGE_SHAPES[i]:
            raise CanonicalEncodingError(f"open-water storage v1 shape drift: {i}")
    manifest = OPEN_WATER_PACK_SCHEMA_V1
    if type(manifest) is not CanonicalSchemaManifest or type(getattr(manifest, "entries", None)) is not tuple:
        raise CanonicalEncodingError("open-water storage v1 binding drift: expected manifest with tuple entries")
    entries = manifest.entries
    if any(type(entry) is not RegisteredTypeEntry for entry in entries):
        raise CanonicalEncodingError("open-water storage v1 binding drift: expected RegisteredTypeEntry instances")
    try:
        CanonicalSchemaManifest.model_validate(manifest, strict=True)
    except ValidationError as exc:
        raise CanonicalEncodingError(f"open-water storage v1 binding drift: {exc}") from exc
    if len(entries) != len(expected) or {e.type_id: (e.python_type, e.kind) for e in entries} != expected:
        raise CanonicalEncodingError("open-water storage v1 binding drift")
    for type_id, names in _V1_WIRE_FIELDS.items():
        if tuple(expected[type_id][0].model_fields) != names:
            raise CanonicalEncodingError(f"open-water v1 wire field binding drift: {type_id}")
    source_types = tuple(entry.python_type for entry in sourceBindings.OPEN_WATER_SOURCE_SCHEMA_V1.entries)
    _, source_aliases = _closure(source_types)
    records, aliases = _closure((*source_types, HydrologyPackRoot, HydrologyPackShard))
    if (records != {owner for owner, _ in expected.values()}
            or aliases.keys() - source_aliases.keys() != {"ArtifactFormatKey", "FormatVersion", "RevisionHex"}):
        raise CanonicalEncodingError("open-water storage v1 closure drift")
    fields = ArtifactRef.model_fields
    if (fields["format_key"].annotation is not ArtifactFormatKey
            or fields["format_version"].annotation is not FormatVersion
            or fields["content_hash"].annotation is not RevisionHex
            or (repr(ArtifactFormatKey.__value__), repr(FormatVersion.__value__), repr(RevisionHex.__value__)) != _ARTIFACT_ALIASES):
        raise CanonicalEncodingError("open-water storage v1 artifact alias drift")


def _require_wire_values(value, owners: frozenset[type]) -> None:
    if isinstance(value, (tuple, frozenset)):
        for child in value:
            _require_wire_values(child, owners)
    elif isinstance(value, (BaseModel, Enum)) or dataclasses.is_dataclass(value):
        if type(value) not in owners:
            raise CanonicalEncodingError(f"unregistered storage v1 type: {type(value).__qualname__}")
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                _require_wire_values(getattr(value, name), owners)
        elif dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                _require_wire_values(getattr(value, field.name), owners)
    elif isinstance(value, str):
        # TLV reconstructs RegistryKey from plain text, which requires min_length=1.
        if isinstance(value, RegistryKey) and not value:
            raise CanonicalEncodingError("empty storage registry key")
        value.encode("utf-8", errors="strict")


def require_pack_record_v1(record: HydrologyPackRoot | HydrologyPackShard) -> None:
    require_pack_schema_v1()
    if type(record) not in (HydrologyPackRoot, HydrologyPackShard):
        raise CanonicalEncodingError("expected exact open-water storage root or shard")
    try:
        type(record).model_validate(record, strict=True)
        _require_wire_values(record, frozenset(e.python_type for e in OPEN_WATER_PACK_SCHEMA_V1.entries))
        if isinstance(record, HydrologyPackRoot):
            require_source_diagnostics_v1(record.diagnostics)
    except (ValueError, TypeError, AttributeError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc


_STORAGE_SHAPES = {
    60001: 'fba09c8adae6fd322b21e30b09dbb940c386889cd9dca7e8735e8b6674a5d691',
    60002: 'd3ffe67598f39312525cfe8ab380ba6019e7133a1c0505dfb8c610e3343a10a2',
    60003: 'fd5cfdba6e4674d58d4aef89ced5adf28a073004b166dc329989e447acff203b',
    60005: 'c26787c76eb2c535951d13feca64a97d7870aa48498db638ddb27afca91b3f41',
    60006: 'af65328a6107bd73c8d1b19c5057e7e496cfc5c67df8b4f897b0b83ea9da4a73',
}
_ARTIFACT_ALIASES = (
    'app.dataModel.registryKey.RegistryKey[app.dataModel.artifacts.references.ArtifactFormatRegistry]',
    'typing.Annotated[int, Strict(strict=True), FieldInfo(annotation=NoneType, required=True, metadata=[Gt(gt=0)])]',
    "typing.Annotated[str, Strict(strict=True), StringConstraints(strip_whitespace=None, to_upper=None, "
    "to_lower=None, strict=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$', ascii_only=None)]",
)
