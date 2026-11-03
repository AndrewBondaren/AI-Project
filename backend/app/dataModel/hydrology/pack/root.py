"""Immutable open-water v1 catalog, provenance and domain tables."""
from dataclasses import fields, is_dataclass
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, StrictInt, TypeAdapter, model_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.encoding.decodeLimits import CollectionLimit
from app.dataModel.hydrology.pack.profile import FORMAT_VERSION, MAX_CONTAINER_ITEMS, SHARD_V1, TILE_SIDE
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.identity.planKey import AlgorithmVersion, PlanSlot, SchemaVersion
from app.dataModel.registryKey import RegistryKey
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable


# Contract revisions captured by storage v1, in canonical slot order.
_DEPENDENCIES: tuple[PlanDependencyContract, ...] = (
    PlanDependencyContract(
        slot=PlanSlot("fine_water"), contract_id=RegistryKey[PlanContractRegistry]("hydrology.fine_water"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(2)),
    PlanDependencyContract(
        slot=PlanSlot("hydrology_routes"), contract_id=RegistryKey[PlanContractRegistry]("hydrology.native_routes"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1)),
    PlanDependencyContract(
        slot=PlanSlot("native_final"), contract_id=RegistryKey[PlanContractRegistry]("hydrology.native_final"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1)),
    PlanDependencyContract(
        slot=PlanSlot("pre_water_surface"), contract_id=RegistryKey[PlanContractRegistry]("terrain.pre_water_window"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(2)),
    PlanDependencyContract(
        slot=PlanSlot("prepared_natural"), contract_id=RegistryKey[PlanContractRegistry]("terrain.prepared_natural"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1)),
    PlanDependencyContract(
        slot=PlanSlot("river_relief"), contract_id=RegistryKey[PlanContractRegistry]("terrain.native_river_relief"),
        schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1)),
    PlanDependencyContract(
        slot=PlanSlot("water_placement"), contract_id=RegistryKey[PlanContractRegistry]("surface.geo.water_placement"),
        schema_version=SchemaVersion(2), algorithm_version=AlgorithmVersion(1)),
)


def require_source_ref(ref: PlanRef) -> None:
    key = ref.key
    if (key.contract_id, key.schema_version, key.algorithm_version) != ("hydrology.canonical_open_water", 1, 1):
        raise ValueError("unsupported open-water source revision")


def _exact(original, admitted):
    """Detect nested coercion, including bool/int and StrEnum/str equality."""
    if type(original) is not type(admitted) or original != admitted:
        raise ValueError("storage field changed under strict admission")
    if isinstance(original, BaseModel):
        for name in type(original).model_fields:
            _exact(getattr(original, name), getattr(admitted, name))
    elif is_dataclass(original):
        for field in fields(original):
            _exact(getattr(original, field.name), getattr(admitted, field.name))
    elif isinstance(original, tuple):
        for before, after in zip(original, admitted, strict=True):
            _exact(before, after)
    elif isinstance(original, frozenset):
        counterparts = {item: item for item in admitted}
        for item in original:
            _exact(item, counterparts[item])


def _validate_nested(value):
    if isinstance(value, BaseModel):
        for child in vars(value).values():
            _validate_nested(child)
        # Legacy models may trust an instance, including a forged model_copy.
        _exact(value, type(value).model_validate(vars(value), strict=True))
    elif isinstance(value, (tuple, frozenset)):
        for child in value:
            _validate_nested(child)


class _PackRecord(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    collection_limits: ClassVar[tuple[CollectionLimit, ...]] = ()

    @model_validator(mode="wrap")
    @classmethod
    def _strict_fields(cls, value, handler):
        raw = vars(value) if isinstance(value, cls) else value
        if not isinstance(raw, dict) or raw.keys() != cls.model_fields.keys():
            raise ValueError("expected complete storage record")
        for rule in cls.collection_limits:
            items = raw[rule.bound.field]
            if type(items) is not tuple or not rule.admits(len(items)):
                raise ValueError(f"invalid storage collection: {rule.bound.field}")
        for field in raw.values():
            validate_immutable(field)
            _validate_nested(field)
        admitted = handler(raw)
        for name, field in raw.items():
            _exact(field, getattr(admitted, name))
        return admitted


class HydrologyShardRef(_PackRecord):
    tx: StrictInt
    ty: StrictInt
    artifact: ArtifactRef

    @model_validator(mode="after")
    def _shard_descriptor(self) -> Self:
        ref = self.artifact
        if (ref.kind is not ArtifactKind.BLOB or ref.format_key != SHARD_V1.key
                or ref.format_version != FORMAT_VERSION or ref.row_count is not None or not 0 < ref.nbytes <= SHARD_V1.max_bytes):
            raise ValueError("invalid open-water shard descriptor")
        return self


def _ordered_ids(values):
    if values != tuple(sorted(set(values))):
        raise ValueError("physical IDs must be unique and sorted")
    for uid in values:
        TypeAdapter(EntityUid).validate_python(uid, strict=True)


class HydrologyPackRoot(_PackRecord):
    source_ref: PlanRef
    dependencies: tuple[PlanDependency, ...]
    diagnostics: tuple[PlanDiagnostic, ...]
    topology: WorldTopology
    coverage_region_uid: EntityUid
    z_min: FineZ
    z_max: FineZ
    bodies: tuple[WaterBody, ...]
    unions: tuple[PhysicalWaterUnion, ...]
    source_mapping: SourceBodyMapping
    shards: tuple[HydrologyShardRef, ...]

    @model_validator(mode="after")
    def _catalog(self) -> Self:
        require_source_ref(self.source_ref)
        if self.z_min > self.z_max:
            raise ValueError("invalid catalog extent")
        if len(self.dependencies) != len(_DEPENDENCIES):
            raise ValueError("unexpected open-water dependency count")
        for expected, dependency in zip(_DEPENDENCIES, self.dependencies, strict=True):
            if not expected.accepts(dependency):
                raise ValueError("unexpected open-water dependency slot or revision")
            key = dependency.ref.key
            if (key.world_uid, key.scope) != (self.source_ref.key.world_uid, self.source_ref.key.scope):
                raise ValueError("dependency belongs to a different world or scope")
        bounds = self.topology.bounds
        tiles = tuple((row.ty, row.tx) for row in self.shards)
        if tiles != tuple(sorted(set(tiles))) or any(
                not bounds.x_min // TILE_SIDE <= tx <= bounds.x_max // TILE_SIDE
                or not bounds.y_min // TILE_SIDE <= ty <= bounds.y_max // TILE_SIDE for ty, tx in tiles):
            raise ValueError("shard tiles must be unique, ordered and intersect the frame")
        self._physical_tables()
        return self

    def _physical_tables(self) -> None:
        _ordered_ids(tuple(body.water_body_uid for body in self.bodies))
        _ordered_ids(tuple(union.water_system_uid for union in self.unions))
        bodies = {body.water_body_uid: body for body in self.bodies}
        unions = {union.water_system_uid: union for union in self.unions}
        members = {uid: set() for uid in unions}
        for fact in (*self.bodies, *self.unions):
            if not self.z_min <= fact.z_water_level <= self.z_max:
                raise ValueError("effective level exceeds source scope")
        for uid, union in unions.items():
            _ordered_ids(union.member_uids)
            _ordered_ids(union.child_system_uids)
            parent = unions.get(union.parent_system_uid) if union.parent_system_uid is not None else None
            if union.parent_system_uid is not None and (parent is None or uid not in parent.child_system_uids
                                                        or union.z_water_level != parent.z_water_level):
                raise ValueError("inconsistent physical parent")
            if any(child not in unions or unions[child].parent_system_uid != uid for child in union.child_system_uids):
                raise ValueError("inconsistent physical children")
            visited = {uid}
            while parent is not None:
                if parent.water_system_uid in visited:
                    raise ValueError("physical union cycle")
                visited.add(parent.water_system_uid)
                parent = unions.get(parent.parent_system_uid) if parent.parent_system_uid is not None else None
        for uid, body in bodies.items():
            parent_uid = body.parent_system_uid
            while parent_uid is not None:
                parent = unions.get(parent_uid)
                if parent is None or body.z_water_level != parent.z_water_level:
                    raise ValueError("inconsistent body ancestry")
                members[parent_uid].add(uid)
                parent_uid = parent.parent_system_uid
        if any(members[uid] != set(union.member_uids) for uid, union in unions.items()):
            raise ValueError("inconsistent physical membership")
        if any(uid not in bodies for entry in self.source_mapping.entries for uid in entry.body_uids):
            raise ValueError("unresolved source mapping body")


HydrologyPackRoot.collection_limits = (
    CollectionLimit(tuple[PlanDependency, ...],
                    ref=FieldRef(lambda: HydrologyPackRoot, lambda root: root.dependencies),
                    minimum=len(_DEPENDENCIES), maximum=len(_DEPENDENCIES)),
    CollectionLimit(tuple[HydrologyShardRef, ...],
                    ref=FieldRef(lambda: HydrologyPackRoot, lambda root: root.shards),
                    maximum=MAX_CONTAINER_ITEMS),
)
