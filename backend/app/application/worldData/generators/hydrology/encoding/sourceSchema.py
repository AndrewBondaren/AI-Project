"""Frozen source v1 schema/admission; no producer, storage or IO binding."""
import dataclasses
import hashlib
import typing
from enum import Enum
from pydantic import BaseModel
from app.encoding.canonicalCodec import CanonicalEncodingError, CanonicalCodec
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanScopeKind
from app.dataModel.planning.identity.planKey import WorldPlanScope
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.planning.identity.planKey import PlanKey
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMappingEntry
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from app.dataModel.validation.diagnostics.fieldPathError import ReferenceIssueReason
from app.dataModel.validation.diagnostics.fieldPathError import ReferenceIssueContext
from app.dataModel.spatial.facing import Facing
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic

_BINDINGS = (
    (23, HydrologyCellRole, CanonicalTypeKind.ENUM),
    (41, BasinKind, CanonicalTypeKind.ENUM),
    (53, WorldTopology, CanonicalTypeKind.RECORD),
    (54, WorldTopologyMode, CanonicalTypeKind.ENUM),
    (55, WorldBounds, CanonicalTypeKind.RECORD),
    (80, HydrologyConnectionType, CanonicalTypeKind.ENUM),
    (94, PlanRef, CanonicalTypeKind.RECORD),
    (95, PlanKey, CanonicalTypeKind.RECORD),
    (96, WorldPlanScope, CanonicalTypeKind.RECORD),
    (97, PlanScopeKind, CanonicalTypeKind.ENUM),
    (98, RegionPlanScope, CanonicalTypeKind.RECORD),
    (101, PlanDependency, CanonicalTypeKind.RECORD),
    (105, PlanDiagnostic, CanonicalTypeKind.RECORD),
    (106, FieldPathError, CanonicalTypeKind.RECORD),
    (107, ReferenceIssueContext, CanonicalTypeKind.RECORD),
    (108, ReferenceIssueReason, CanonicalTypeKind.ENUM),
    (109, RuntimeIssueContext, CanonicalTypeKind.RECORD),
    (110, Facing, CanonicalTypeKind.ENUM),
    (111, PlanDiagnosticDisposition, CanonicalTypeKind.ENUM),
    (119, CoordinateSpace, CanonicalTypeKind.ENUM),
    (150, MapCellHydrology, CanonicalTypeKind.RECORD),
    (151, HydrologyShoreKind, CanonicalTypeKind.ENUM),
    (152, RiverDrainageLink, CanonicalTypeKind.RECORD),
    (153, WaterBody, CanonicalTypeKind.RECORD),
    (154, PhysicalWaterUnion, CanonicalTypeKind.RECORD),
    (226, SourceBodyMapping, CanonicalTypeKind.RECORD),
    (227, SourceBodyMappingEntry, CanonicalTypeKind.RECORD),
    (238, RegionCoverage, CanonicalTypeKind.RECORD),
    (239, CoverageSpan, CanonicalTypeKind.RECORD),
    (283, FineSurfaceWindow, CanonicalTypeKind.RECORD),
    (60004, WaterMembershipRun, CanonicalTypeKind.RECORD),
    (60007, CanonicalOpenWaterSource, CanonicalTypeKind.RECORD),
    (60008, PlanEnvelope[CanonicalOpenWaterSource], CanonicalTypeKind.RECORD),
)
OPEN_WATER_SOURCE_SCHEMA_V1 = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=i, python_type=t, kind=k) for i, t, k in _BINDINGS))

# Accepted В§15.13 shapes filtered by В§15.18; not regenerated at runtime.
_SHAPE_LOCK = {
    23: 'f6dc9702515c8f53f1f206f64d5c339711bc0cf8f17f3daf8a0b790bf91c755d',
    41: '51f055562ec5eb98a4d02383f42e17e7b1f134fc67569c5817df084b9afe821b',
    53: 'ee3bbd3d85f654aafc79ba6b3ed0896333f60e4d04b4114b606fbae8a300cf2e',
    54: 'ea7c399a63b756b63700b0e174ed64d549552865a5f3833158a224e88e8a97ee',
    55: 'd39b9a96f70574787a02e92c3e842c0ad146b0601468b2aab3d4bb265b73cc5c',
    80: 'c69516c32c9ea7c398d22985ff0d56ee0b278e215b61bc4d563286050ea91ec8',
    94: 'cf48a467951b37262e19bc327a6da09d8de97ae115043419a4ee6429f7378ff7',
    95: '539e43f09920e6481e83557e87749d87ea65d86bf99a60fe976bc5ad10e3845f',
    96: '9bad18859a5f7716369ce497254d1112f856f5433500a55b5ef18465b16e6b6a',
    97: 'e15fe7a7051d0bf3586188206708f8cb796bf1472c6b975e68fa9f605cba3e36',
    98: 'e8d87246501591f9a651a20d2d4410b806b341cd0b4de4e403fd8638fba59535',
    101: 'df0b61446b0b0fafa24a6ef90d7e9fda3aa78f2b2e7911909a78f5f820fa27d2',
    105: '0015cc93674db4560d43f3bebdb83b02475aa0edb9f6425e83becd0c46308d2f',
    106: '7a1ca9ab332d57a29ed37c5ed0f5fe66b05ffe524a0408f595721556e7aa0e59',
    107: '32ab6b65a79277614d3357785d2288e0a3e2c55c5ffc5a6bf6d800ca5d115240',
    108: '3dd5926a3bcd0629cf785612bbe5c2a487daffd5e6b1c596027c845c19b2fbec',
    109: '2d38f58e76f621ae727a05f05187370d7dd7d30f5646e3f136c6a36c038aa6db',
    110: 'ded1358ff3073ac7bf472acfe2c3e114ec38c8840b265e545b63976c9dd04294',
    111: 'fb3ecb9943341240bd6a8419ef935263cc708ccb4af065f0d0df23ae2fb8a1e1',
    119: 'cc3e5814d6d48f5f15b4096bee08b5bafbf276402adb78a67ef2d72df137e002',
    150: 'cba612a16a2b6b2d6f074d54c9a75b5ecc565fb6ddad153d7d3cf5f17d356b82',
    151: '169f3300fe83a9ba41883693007eff84ff93b6b13daa06b70f98afa4b5ff2ae9',
    152: '485b7653d94ea1c712775dd411aaba40605ec969bfe3f6b3b96339e269bf9005',
    153: '02e08cd59013b5a6cd2b76f5991b3ed4c5ea09a1c8a2576f4b1e1d97b435d52c',
    154: '83403528aa7d9428f00a2d599fb88efd1dffefabb16db5031bb1c074547b2569',
    226: '26c841e751a0668d397864383ce4d0946c9af014add70318731f6dfe04446b02',
    227: 'ef79f40acc1f27294d6b14cc7614046e92ee77cc21e5f1d211bbbedf7deccc15',
    238: '268fe82c9c4f4be748367502830b4607a1d79f44a15b80d14cb8446070ede9da',
    239: 'eba4c0cf5e21b38a1b06897c7493ff1706eb6443d44593bc6afde1a97274f149',
    283: '132dd37e262f58d558395eb51baac774411f6988eb8a59e1be68fd5a7b34c627',
    60004: 'd50b0a127135dd592d24a70e033c4bc917ef7e9f4cdc8d77c6a189d6b8c7babc',
    60007: '0a404488b1ee2845170980a2de6ca8d3a92cccae652ec1cdd1483d4654d10f70',
    60008: '4054d88e4b66eebe6c49da0f85dadafc9119eb7f13218432f2929c380861878b',
}

_ALIAS_LOCK = (
    ('AlgorithmVersion', "<class 'int'>"),
    ('EntityUid', "typing.Annotated[str, Strict(strict=True), StringConstraints(strip_whitespace=None, to_upper=None, to_lower=None, strict=None, min_length=1, max_length=None, pattern='^\\\\S(?:.*\\\\S)?$', ascii_only=None)]"),
    ('FineX', "<class 'int'>"),
    ('FineXY', 'tuple[app.dataModel.spatial.grid.coordinateTypes.FineX, app.dataModel.spatial.grid.coordinateTypes.FineY]'),
    ('FineY', "<class 'int'>"),
    ('FineZ', "<class 'int'>"),
    ('InputFingerprint', "<class 'bytes'>"),
    ('MaterialKey', 'app.dataModel.registryKey.RegistryKey[app.dataModel.materials.worldMaterialRegistry.WorldMaterialRegistry]'),
    ('OutputFingerprint', "<class 'bytes'>"),
    ('PlanContractId', 'app.dataModel.registryKey.RegistryKey[app.dataModel.planning.contracts.planContract.PlanContractRegistry]'),
    ('PlanScope', "typing.Annotated[app.dataModel.planning.identity.planKey.WorldPlanScope | app.dataModel.planning.identity.planKey.RegionPlanScope, FieldInfo(annotation=NoneType, required=True, discriminator='kind')]"),
    ('PlanSlot', "<class 'str'>"),
    ('RevisionHex', "typing.Annotated[str, Strict(strict=True), StringConstraints(strip_whitespace=None, to_upper=None, to_lower=None, strict=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$', ascii_only=None)]"),
    ('SchemaVersion', "<class 'int'>"),
)

def _snapshot():
    seen, aliases, shapes = set(), {}, {}
    alias_owners = {}

    def walk(owner):
        if isinstance(owner, (typing.TypeAliasType, typing.NewType)):
            name = owner.__name__
            if name in alias_owners:
                if alias_owners[name] is not owner:
                    raise CanonicalEncodingError(f"open-water source v1 alias collision: {name}")
                return
            alias_owners[name] = owner
            target = owner.__value__ if isinstance(owner, typing.TypeAliasType) else owner.__supertype__
            aliases[name] = repr(target)
            walk(target)
            return
        if isinstance(owner, Enum):
            walk(type(owner))
            return
        origin = typing.get_origin(owner)
        if origin is not None and dataclasses.is_dataclass(origin):
            walk(origin)
        if origin is RegistryKey:  # registry parameter is phantom, not payload
            return
        for argument in typing.get_args(owner):
            walk(argument)
        if not isinstance(owner, type) or owner in seen:
            return
        if not (issubclass(owner, (BaseModel, Enum)) or dataclasses.is_dataclass(owner)):
            return
        seen.add(owner)
        if issubclass(owner, Enum):
            if not owner.__members__:  # abstract StrEnum
                return
            shape = "; ".join(n + "=" + repr(getattr(v, "wire_value", v.value))
                              for n, v in owner.__members__.items())
        else:
            model = issubclass(owner, BaseModel)
            fields = owner.model_fields if model else {f.name: f for f in dataclasses.fields(owner)}
            hints = typing.get_type_hints(owner, include_extras=True)
            parts = []
            for name, field in fields.items():
                annotation = field.annotation if model else hints[name]
                walk(annotation)
                default = "MISSING" if field.default is dataclasses.MISSING else repr(field.default)
                factory = getattr(field, "default_factory", None)
                if factory is not None and factory is not dataclasses.MISSING:
                    default = "factory→" + repr(factory())
                metadata = "; metadata=" + repr(field.metadata) if hasattr(field, "metadata") else ""
                parts.append(name + ": " + repr(annotation) + "; default=" + default + metadata)
            shape = "<br>".join(parts)
        qualified = owner.__module__ + "." + owner.__name__
        shapes[owner] = hashlib.sha256((qualified + "\n" + shape).encode()).hexdigest()

    walk(PlanEnvelope[CanonicalOpenWaterSource])
    return shapes, tuple(sorted(aliases.items()))


def require_source_schema_v1() -> None:
    """Refuse lock drift before encoding/fingerprinting; no registry mutation."""
    try:
        bindings = tuple((e.type_id, e.python_type, e.kind) for e in OPEN_WATER_SOURCE_SCHEMA_V1.entries)
        if bindings != _BINDINGS:
            raise CanonicalEncodingError("open-water source v1 ID binding drift")
        shapes, aliases = _snapshot()
        if set(shapes) != {owner for _, owner, _ in _BINDINGS}:
            raise CanonicalEncodingError("open-water source v1 closure drift")
        for identity, owner, _ in _BINDINGS:
            if shapes[owner] != _SHAPE_LOCK[identity]:
                raise CanonicalEncodingError(f"open-water source v1 shape drift: {identity}")
        if aliases != _ALIAS_LOCK:
            raise CanonicalEncodingError("open-water source v1 alias drift")
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc


# Emitted code/disposition pairs frozen for source v1 in Spatial §15.18.1.
_PRODUCER_DISPOSITIONS = {
    "WATER_PUDDLE": PlanDiagnosticDisposition.ERROR,
    "WATER_CANNOT_HOLD": PlanDiagnosticDisposition.ERROR,
    "WATER_TERRAIN_UNRESOLVED": PlanDiagnosticDisposition.ERROR,
    "WATER_NO_OCEAN_DEPRESSION": PlanDiagnosticDisposition.ERROR,
    "WATER_KIND_MISMATCH": PlanDiagnosticDisposition.FALLBACK,
    "WATER_LEVEL_SPILL": PlanDiagnosticDisposition.FALLBACK,
    "WATER_LEVEL_SUPERSEDED": PlanDiagnosticDisposition.FALLBACK,
    "WATER_WORLD_OCEAN": PlanDiagnosticDisposition.NOTICE,
    "RIVER_REDIRECTED": PlanDiagnosticDisposition.FALLBACK,
    "RIVER_INVALID_CONNECTION_TYPE": PlanDiagnosticDisposition.ERROR,
    "RIVER_INVALID_SOURCE": PlanDiagnosticDisposition.ERROR,
    "RIVER_TARGET_UNREACHABLE": PlanDiagnosticDisposition.ERROR,
    "RIVER_NO_WATER_BODIES": PlanDiagnosticDisposition.ERROR,
    "RIVER_NO_REACHABLE_WATER": PlanDiagnosticDisposition.ERROR,
}


def require_source_diagnostics_v1(diagnostics: tuple[PlanDiagnostic, ...]) -> None:
    """Validate unchanged producer diagnostics; optional branches are not admission."""
    require_source_schema_v1()
    if type(diagnostics) is not tuple:
        raise CanonicalEncodingError("source diagnostics must be an immutable tuple")
    try:
        for diagnostic in diagnostics:
            if type(diagnostic) is not PlanDiagnostic or type(diagnostic.issue) is not FieldPathError:
                raise CanonicalEncodingError("unexpected source diagnostic record")
            issue = diagnostic.issue
            if issue.reference is not None or issue.runtime_context is not None:
                raise CanonicalEncodingError("unadmitted producer diagnostic context")
            # TLV encodes enum subclasses with a different tag from plain scalars.
            if type(issue.message) is not str or (issue.schema_id is not None and type(issue.schema_id) is not str):
                raise CanonicalEncodingError("expected plain diagnostic message and optional schema ID")
            if type(issue.path) is not tuple or any(type(part) not in (str, int) for part in issue.path):
                raise CanonicalEncodingError("expected diagnostic path of plain strings and integers")
            code = issue.code
            if type(code) is not str or code not in _PRODUCER_DISPOSITIONS or (
                    diagnostic.disposition is not _PRODUCER_DISPOSITIONS[code]):
                raise CanonicalEncodingError(f"unadmitted producer diagnostic pair for {code!r}")
        CanonicalCodec(OPEN_WATER_SOURCE_SCHEMA_V1).encode(diagnostics)
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc
