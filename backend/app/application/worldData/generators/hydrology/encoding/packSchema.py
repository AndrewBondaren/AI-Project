"""Open-water storage v1 bindings and in-process record admission."""
import dataclasses
import typing
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, ValidationError

from app.encoding.canonicalCodec import CanonicalEncodingError
from app.application.worldData.generators.hydrology.encoding.sourceSchema import (
    OPEN_WATER_SOURCE_SCHEMA_V1, require_source_diagnostics_v1, require_source_schema_v1,
)
from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactKind, ArtifactRef, FormatVersion
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.hydrology.pack.root import HydrologyPackRoot, HydrologyShardRef
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.registryKey import RegistryKey


_STORAGE = (
    (60001, HydrologyPackRoot), (60002, HydrologyShardRef), (60003, HydrologyPackShard),
    (60005, ArtifactRef), (60006, ArtifactKind),
)
OPEN_WATER_PACK_SCHEMA_V1 = CanonicalSchemaManifest(entries=tuple(sorted((
    *OPEN_WATER_SOURCE_SCHEMA_V1.entries,
    *(RegisteredTypeEntry(type_id=i, python_type=t,
                          kind=CanonicalTypeKind.ENUM if issubclass(t, Enum) else CanonicalTypeKind.RECORD)
      for i, t in _STORAGE)), key=lambda entry: entry.type_id)))


# Stable ordered TLV field identifiers. V1 binds each identifier to the same POJO name.
_V1_WIRE_FIELDS = {
    53: ('mode', 'bounds'),
    55: ('x_min', 'x_max', 'y_min', 'y_max'),
    94: ('key', 'output_fingerprint'),
    95: ('world_uid', 'scope', 'contract_id', 'schema_version', 'algorithm_version', 'input_fingerprint'),
    96: ('kind',),
    98: ('kind', 'region_uid'),
    101: ('slot', 'ref'),
    105: ('issue', 'disposition'),
    106: ('path', 'message', 'schema_id', 'code', 'reference', 'runtime_context'),
    107: ('reason', 'domain', 'world_uid', 'requested_template_uid', 'owner_pack_uid', 'dependency_pack_uid', 'consumer', 'selected_default'),
    109: ('world_uid', 'snapshot_uid', 'content_revision', 'source_uid', 'body_uids', 'cell', 'face', 'fallback_action', 'fallback_reason'),
    150: ('liquid_candidate', 'role', 'deepening_index', 'connection_edge_uid', 'shore_kind', 'water_body_uid', 'z_water_level', 'river_drainage'),
    152: ('river_uid', 'river_type', 'receiver_uid', 'receiver_kind', 'receiver_cell'),
    153: ('water_body_uid', 'location_uid', 'kind', 'liquid', 'declared_level', 'z_water_level', 'declared_basin_uid', 'parent_system_uid'),
    154: ('water_system_uid', 'member_uids', 'child_system_uids', 'z_water_level', 'parent_system_uid'),
    226: ('entries',),
    227: ('source_uid', 'body_uids'),
    238: ('region_uid', 'spans'),
    239: ('y', 'x0', 'x1'),
    283: ('coverage', 'surface_z', 'topology', 'protected_cells'),
    60001: ('source_ref', 'dependencies', 'diagnostics', 'topology', 'coverage_region_uid', 'z_min', 'z_max', 'bodies', 'unions', 'source_mapping', 'shards'),
    60002: ('tx', 'ty', 'artifact'),
    60003: ('source_ref', 'tx', 'ty', 'bed', 'wet_runs', 'shore_rows'),
    60004: ('y', 'x0', 'x1', 'body_uid'),
    60005: ('kind', 'format_key', 'format_version', 'content_hash', 'nbytes', 'row_count'),
    60007: ('space', 'bed', 'z_min', 'z_max', 'wet_runs', 'bodies', 'unions', 'source_mapping', 'shore_rows'),
    60008: ('ref', 'dependencies', 'payload', 'diagnostics'),
}


def _shape(owner):
    name = owner.__module__ + "." + owner.__name__
    if issubclass(owner, Enum):
        rows = [(key, getattr(member, "wire_value", member.value)) for key, member in owner.__members__.items()]
    else:
        rows = [(key, repr(field.annotation), repr(field.default), repr(field.default_factory), repr(field.metadata))
                for key, field in owner.model_fields.items()]
    return sha256(repr((name, rows)).encode()).hexdigest()


def _closure():
    """Include the frozen source schema and the two concrete storage roots."""
    pending = [PlanEnvelope[CanonicalOpenWaterSource], HydrologyPackRoot, HydrologyPackShard]
    records = set()
    aliases = {}
    while pending:
        owner = pending.pop()
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
    expected = {e.type_id: (e.python_type, e.kind) for e in OPEN_WATER_SOURCE_SCHEMA_V1.entries}
    for i, owner in _STORAGE:
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
    for entry in entries:
        if entry.kind is CanonicalTypeKind.RECORD:
            owner = entry.python_type
            names = tuple(owner.model_fields) if issubclass(owner, BaseModel) else tuple(
                field.name for field in dataclasses.fields(owner))
            if names != _V1_WIRE_FIELDS.get(entry.type_id):
                raise CanonicalEncodingError(f"open-water v1 wire field binding drift: {entry.type_id}")
    records, aliases = _closure()
    if records != {owner for owner, _ in expected.values()} or len(aliases) != 16:
        raise CanonicalEncodingError("open-water storage v1 closure drift")
    fields = ArtifactRef.model_fields
    if (fields["format_key"].annotation is not ArtifactFormatKey
            or fields["format_version"].annotation is not FormatVersion
            or (repr(ArtifactFormatKey.__value__), repr(FormatVersion.__value__)) != _ARTIFACT_ALIASES):
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
    60001: '12d05e7623678f7bda180f479341f828f46eb96fc0c64f85d506becceedf2232',
    60002: 'd3ffe67598f39312525cfe8ab380ba6019e7133a1c0505dfb8c610e3343a10a2',
    60003: 'fd5cfdba6e4674d58d4aef89ced5adf28a073004b166dc329989e447acff203b',
    60005: 'c26787c76eb2c535951d13feca64a97d7870aa48498db638ddb27afca91b3f41',
    60006: 'af65328a6107bd73c8d1b19c5057e7e496cfc5c67df8b4f897b0b83ea9da4a73',
}
_ARTIFACT_ALIASES = (
    'app.dataModel.registryKey.RegistryKey[app.dataModel.artifacts.references.ArtifactFormatRegistry]',
    'typing.Annotated[int, Strict(strict=True), FieldInfo(annotation=NoneType, required=True, metadata=[Gt(gt=0)])]',
)
