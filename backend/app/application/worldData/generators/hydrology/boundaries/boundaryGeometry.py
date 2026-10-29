"""Authored fine path association with actual final wet/dry evidence."""

from dataclasses import dataclass
from fractions import Fraction

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.dataModel.hydrology.boundaries.attachedCoastline import AttachedCoastline, BoundaryIssueCode, CoastlinePart
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_UID = TypeAdapter(EntityUid)


def boundary_failure(source: DeclaredCoastline, code: BoundaryIssueCode, message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("coastline_boundary", source.location_uid), message, code=code.value),))


@dataclass(frozen=True)
class BoundaryGeometryResult:
    """Public geometry result: one boundary metadata record and its canonical raster."""

    boundary: AttachedCoastline
    cells: frozenset[Coord]


class BoundaryGeometry:
    """No policy or height writes: preserve the path's raster and label contiguous parts."""

    def prepare(self, source: DeclaredCoastline, snapshot: BoundaryWaterSnapshot) -> BoundaryGeometryResult:
        if not isinstance(source, DeclaredCoastline) or not isinstance(snapshot, BoundaryWaterSnapshot):
            raise TypeError("boundary geometry requires typed source and final-water snapshot")
        source = DeclaredCoastline.model_validate(source.model_dump(warnings=False), strict=True)
        snapshot = BoundaryWaterSnapshot.model_validate(snapshot, strict=True)
        _UID.validate_python(source.location_uid, strict=True)
        target = source.target_source_uid
        if source.purpose is not CoastlinePurpose.BODY_BOUNDARY or target is None or target == source.location_uid:
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "boundary requires a distinct explicit water-source target")
        entry = next((entry for entry in snapshot.source_mapping.entries if entry.source_uid == target), None)
        if entry is None or not entry.body_uids:
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "ready boundary requires nonempty authoritative target mapping")
        target_bodies = frozenset(entry.body_uids)
        topology = fine_topology(snapshot.topology, snapshot.grid.fine_span)
        occupancy: dict[Coord, EntityUid | None] = {sample.cell: sample.body_uid for sample in snapshot.fine_cells}
        trace = self._trace(source)
        labels: list[frozenset[EntityUid]] = []
        canonical_cells: set[Coord] = set()
        for point in trace:
            cell = topology.canonicalize(point.x, point.y)
            if cell is None:
                raise boundary_failure(source, BoundaryIssueCode.BOUNDARY_OFF_TARGET, "absolute path leaves the planar world")
            canonical_cells.add(cell)
            stencil = {cell}
            for facing in sorted(CARDINAL_FACINGS, key=lambda facing: facing.value):
                neighbor = topology.neighbor(*cell, facing)
                if neighbor is not None:
                    stencil.add(neighbor.coord)
            missing = sorted(stencil - occupancy.keys(), key=lambda cell: (cell[1], cell[0]))
            if missing:
                raise boundary_failure(source, BoundaryIssueCode.UNKNOWN_FINE_WATER,
                    f"missing final fine water evidence for {missing[0]}")
            observed = tuple(occupancy[cell] for cell in sorted(stencil))
            bodies = frozenset(uid for uid in observed if uid is not None and uid in target_bodies)
            # Other water is not land. Planar void is not an observed dry cell.
            if not bodies or None not in observed:
                raise boundary_failure(source, BoundaryIssueCode.BOUNDARY_OFF_TARGET,
                    f"authored path cell {(point.x, point.y)} is not on target wet/dry boundary")
            labels.append(bodies)
        parts: list[CoastlinePart] = []
        for body_uid in sorted(frozenset(uid for bodies in labels for uid in bodies)):
            membership = tuple(body_uid in bodies for bodies in labels)
            if all(membership):
                parts.append(CoastlinePart(body_uid=body_uid, closed=source.closed, path=source.path))
                continue
            runs: list[list[HydrologyWaypoint]] = []
            previous = False
            for point, belongs in zip(trace, membership):
                if belongs:
                    if not runs or not previous:
                        runs.append([])
                    runs[-1].append(point)
                previous = belongs
            if source.closed and membership[0] and membership[-1]:
                runs = [runs[-1] + runs[0], *runs[1:-1]]
            parts.extend(CoastlinePart(body_uid=body_uid, closed=False, path=tuple(run)) for run in runs)
        boundary = AttachedCoastline(source_uid=source.location_uid, target_source_uid=target, parts=tuple(parts),
            coordinate_space=CoordinateSpace.WORLD_FINE_GRID, hydrology_ref=snapshot.hydrology.ref)
        return BoundaryGeometryResult(boundary=boundary, cells=frozenset(canonical_cells))

    @staticmethod
    def _trace(source: DeclaredCoastline) -> tuple[HydrologyWaypoint, ...]:
        """Keep unrolled coordinates through rasterization, including seam crossings.

        Split-point Z is an exact rational interpolation rounded to the nearest
        integer (ties to even). It is path metadata, never a surface write.
        """
        pairs = list(zip(source.path, source.path[1:]))
        first, last = source.path[0], source.path[-1]
        if source.closed and (last.x, last.y) != (first.x, first.y):
            pairs.append((last, first))
        points: list[HydrologyWaypoint] = []
        for start, end in pairs:
            cells = bresenham_line(start.x, start.y, end.x, end.y)
            length = len(cells) - 1
            for index, (x, y) in enumerate(cells):
                if points and (points[-1].x, points[-1].y) == (x, y):
                    continue
                z = start.z if not length else round(Fraction(start.z * (length - index) + end.z * index, length))
                points.append(HydrologyWaypoint(x=x, y=y, z=z))
        if source.closed and (points[-1].x, points[-1].y) == (points[0].x, points[0].y):
            points.pop()
        return tuple(points)
