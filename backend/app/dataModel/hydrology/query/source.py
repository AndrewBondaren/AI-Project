"""Immutable R1 membership and G1 final-bed facts; no solving or publication."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineXY, FineY, FineZ
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable


class WaterSourceIssueCode(StrEnum):
    INVALID_FRAME = "water_source_invalid_frame"
    REVISION_MISMATCH = "water_source_revision_mismatch"
    INCOMPLETE = "water_source_incomplete"
    INVALID_FACT = "water_source_invalid_fact"
    RESOURCE_LIMIT = "water_source_resource_limit"


def _integer(value: object) -> None:
    if type(value) is not int:
        raise ValueError("canonical coordinates and levels require strict integers")


def _coordinate(value: object) -> None:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("canonical cell requires a coordinate tuple")
    for component in value:
        _integer(component)


def _record[T: BaseModel](value: object, model: type[T]) -> T:
    if not isinstance(value, model):
        raise ValueError(f"canonical source requires an actual {model.__name__}")
    validate_immutable(value)
    if set(vars(value)) != set(model.model_fields):
        raise ValueError("canonical nested record has missing or extra fields")
    return value


def _ordered_uids(values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError("physical UIDs must be sorted and unique")
    for uid in values:
        TypeAdapter(EntityUid).validate_python(uid, strict=True)


class WaterMembershipRun(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    y: Annotated[FineY, Field(strict=True)]
    x0: Annotated[FineX, Field(strict=True)]
    x1: Annotated[FineX, Field(strict=True)]
    body_uid: EntityUid

    @model_validator(mode="before")
    @classmethod
    def _strict_coordinates(cls, value: object) -> object:
        if isinstance(value, cls):
            validate_immutable(value)
            value = vars(value)
        if isinstance(value, dict):
            for name in ("y", "x0", "x1"):
                if name in value:
                    _integer(value[name])
        return value

    @model_validator(mode="after")
    def _ordered_run(self) -> Self:
        if self.x0 >= self.x1:
            raise ValueError("water membership requires x0 < x1")
        validate_immutable(self)
        return self


class CanonicalOpenWaterSource(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    space: Literal[CoordinateSpace.WORLD_FINE_GRID]
    bed: FineSurfaceWindow
    z_min: Annotated[FineZ, Field(strict=True)]
    z_max: Annotated[FineZ, Field(strict=True)]
    wet_runs: tuple[WaterMembershipRun, ...]
    bodies: tuple[WaterBody, ...]
    unions: tuple[PhysicalWaterUnion, ...]
    source_mapping: SourceBodyMapping
    shore_rows: tuple[tuple[FineXY, MapCellHydrology], ...]

    @model_validator(mode="before")
    @classmethod
    def _admit_nested(cls, value: object) -> object:
        if isinstance(value, cls):
            validate_immutable(value)
            value = vars(value)
        if not isinstance(value, dict):
            return value
        if value.get("space") is not CoordinateSpace.WORLD_FINE_GRID:
            raise ValueError("canonical source requires the actual world-fine space enum")
        for name in ("z_min", "z_max"):
            if name in value:
                _integer(value[name])
        data = dict(value)
        bed = _record(data.get("bed"), FineSurfaceWindow)
        topology = _record(bed.topology, WorldTopology)
        bounds = _record(topology.bounds, WorldBounds)
        if not isinstance(topology.mode, WorldTopologyMode):
            raise ValueError("canonical source requires an actual topology mode")
        for number in (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max):
            _integer(number)
        if bounds.x_min > bounds.x_max or bounds.y_min > bounds.y_max:
            raise ValueError("canonical source requires ordered topology bounds")
        if topology.mode is WorldTopologyMode.SPHERE and bounds.width % 2:
            raise ValueError("canonical sphere frame requires even width without normalization")
        # Immutability does not establish nested field types on forged instances.
        # Check shapes before traversal, while facts are still pre-normalization.
        coverage = _record(bed.coverage, RegionCoverage)
        if not isinstance(coverage.spans, tuple):
            raise ValueError("coverage spans require an immutable tuple")
        for raw_span in coverage.spans:
            span = _record(raw_span, CoverageSpan)
            for number in (span.y, span.x0, span.x1):
                _integer(number)
        if not isinstance(bed.surface_z, tuple):
            raise ValueError("surface rows require an immutable tuple")
        for row in bed.surface_z:
            if not isinstance(row, tuple) or len(row) != 2:
                raise ValueError("surface row requires a cell/height tuple")
            cell, height = row
            _coordinate(cell)
            _integer(height)
        if not isinstance(bed.protected_cells, frozenset):
            raise ValueError("protected cells require an immutable frozenset")
        for cell in bed.protected_cells:
            _coordinate(cell)
        # Revalidate complete nested values explicitly; legacy models do not opt in.
        data["bed"] = FineSurfaceWindow.model_validate(bed.model_dump(round_trip=True, warnings=False), strict=True)
        mapping = _record(data.get("source_mapping"), SourceBodyMapping)
        data["source_mapping"] = SourceBodyMapping.model_validate(mapping.model_dump(round_trip=True, warnings=False), strict=True)
        for field, model in (("wet_runs", WaterMembershipRun), ("bodies", WaterBody),
                             ("unions", PhysicalWaterUnion)):
            rows = data.get(field)
            if not isinstance(rows, tuple):
                raise ValueError(f"{field} requires an immutable tuple")
            admitted = []
            for row in rows:
                record = _record(row, model)
                if isinstance(record, WaterBody):
                    _integer(record.declared_level)
                    _integer(record.z_water_level)
                elif isinstance(record, PhysicalWaterUnion):
                    _integer(record.z_water_level)
                admitted.append(model.model_validate(record.model_dump(round_trip=True, warnings=False), strict=True))
            data[field] = tuple(admitted)
        shores = data.get("shore_rows")
        if not isinstance(shores, tuple):
            raise ValueError("shore_rows requires an immutable tuple")
        admitted_shores = []
        for row in shores:
            if not isinstance(row, tuple) or len(row) != 2:
                raise ValueError("shore row requires a cell/fact tuple")
            cell, raw_fact = row
            _coordinate(cell)
            fact = _record(raw_fact, MapCellHydrology)
            if fact.role is not HydrologyCellRole.SHORE or fact.liquid_candidate is not False:
                raise ValueError("shore rows require non-liquid SHORE facts")
            if fact.z_water_level is not None:
                _integer(fact.z_water_level)
            if fact.deepening_index is not None:
                _integer(fact.deepening_index)
            TypeAdapter(MapCellHydrology.model_fields["shore_kind"].annotation).validate_python(
                fact.shore_kind, strict=True)
            admitted_shores.append((cell, MapCellHydrology.model_validate(
                fact.model_dump(round_trip=True, warnings=False), strict=True)))
        data["shore_rows"] = tuple(admitted_shores)
        return data

    @model_validator(mode="after")
    def _consistent_source(self) -> Self:
        validate_immutable(self)
        if self.z_min > self.z_max:
            raise ValueError("canonical source requires z_min <= z_max")
        heights = dict(self.bed.surface_z)
        if any(not self.z_min <= z <= self.z_max for z in heights.values()):
            raise ValueError("final bed exceeds source vertical scope")
        _ordered_uids(tuple(body.water_body_uid for body in self.bodies))
        _ordered_uids(tuple(union.water_system_uid for union in self.unions))
        bodies = {body.water_body_uid: body for body in self.bodies}
        unions = {union.water_system_uid: union for union in self.unions}
        for body in self.bodies:
            if not self.z_min <= body.z_water_level <= self.z_max:
                raise ValueError("effective body level exceeds source vertical scope")
            if body.parent_system_uid is not None and body.parent_system_uid not in unions:
                raise ValueError("body parent union is missing")
        for union in self.unions:
            _ordered_uids(union.member_uids)
            _ordered_uids(union.child_system_uids)
            if not self.z_min <= union.z_water_level <= self.z_max:
                raise ValueError("effective union level exceeds source vertical scope")
            if any(uid not in bodies for uid in union.member_uids):
                raise ValueError("union member body is missing")
            if any(uid not in unions for uid in union.child_system_uids):
                raise ValueError("child union is missing")
            if union.parent_system_uid is not None and union.parent_system_uid not in unions:
                raise ValueError("union parent is missing")
        # Iterative ancestry checks avoid recursion limits on authored hierarchies.
        for union in self.unions:
            ancestors: set[str] = set()
            current = union
            while True:
                uid = current.water_system_uid
                if uid in ancestors:
                    raise ValueError("physical union cycle")
                ancestors.add(uid)
                if current.parent_system_uid is None:
                    break
                parent = unions[current.parent_system_uid]
                if uid not in parent.child_system_uids:
                    raise ValueError("union parent/child relationship is inconsistent")
                if not set(current.member_uids) <= set(parent.member_uids):
                    raise ValueError("child members must belong to the parent union")
                if current.z_water_level != parent.z_water_level:
                    raise ValueError("physical ancestors require the same effective level")
                current = parent
            for child_uid in union.child_system_uids:
                if unions[child_uid].parent_system_uid != union.water_system_uid:
                    raise ValueError("union child/parent relationship is inconsistent")
            for member in union.member_uids:
                body = bodies[member]
                current_uid = body.parent_system_uid
                seen: set[str] = set()
                while current_uid is not None and current_uid != union.water_system_uid:
                    if current_uid in seen:
                        raise ValueError("physical union cycle")
                    seen.add(current_uid)
                    current_uid = unions[current_uid].parent_system_uid
                if current_uid is None or body.z_water_level != union.z_water_level:
                    raise ValueError("member body ancestry/effective level is inconsistent")
        for body in self.bodies:
            if body.parent_system_uid is not None:
                parent = unions[body.parent_system_uid]
                if body.water_body_uid not in parent.member_uids or body.z_water_level != parent.z_water_level:
                    raise ValueError("body parent membership/effective level is inconsistent")
        if any(uid not in bodies for entry in self.source_mapping.entries for uid in entry.body_uids):
            raise ValueError("source mapping body is missing")
        previous: WaterMembershipRun | None = None
        wet_cells: set[FineXY] = set()
        for run in self.wet_runs:
            if previous is not None and (
                run.y < previous.y or run.y == previous.y and (
                    run.x0 < previous.x1 or run.x0 == previous.x1 and run.body_uid == previous.body_uid
                )
            ):
                raise ValueError("wet runs must be sorted, disjoint and same-body adjacent runs merged")
            if run.body_uid not in bodies:
                raise ValueError("wet run body is missing")
            level = bodies[run.body_uid].z_water_level
            for x in range(run.x0, run.x1):
                cell = (FineX(x), run.y)
                if cell not in heights:
                    raise ValueError("wet run lies outside observed bed coverage")
                if heights[cell] >= level:
                    raise ValueError("wet membership requires bed_z < effective level")
                wet_cells.add(cell)
            previous = run
        shore_order = tuple((cell[1], cell[0]) for cell, _ in self.shore_rows)
        if shore_order != tuple(sorted(set(shore_order))):
            raise ValueError("shore rows must be sorted and unique")
        for cell, fact in self.shore_rows:
            if cell not in heights or cell in wet_cells:
                raise ValueError("shore must be observed and outside wet membership")
            if fact.water_body_uid is not None:
                if fact.water_body_uid not in bodies:
                    raise ValueError("shore body is missing")
                if fact.z_water_level is not None and fact.z_water_level != bodies[fact.water_body_uid].z_water_level:
                    raise ValueError("shore effective level disagrees with its body")
            if fact.z_water_level is not None and not self.z_min <= fact.z_water_level <= self.z_max:
                raise ValueError("shore level exceeds source vertical scope")
        return self
