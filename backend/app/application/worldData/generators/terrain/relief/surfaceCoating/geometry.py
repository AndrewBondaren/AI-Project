"""Observe stamped mountain sides using their existing geometry/profile kernels."""
from dataclasses import dataclass

from app.application.worldData.generators.terrain.mountains.formGeometry import construct_mountain_form
from app.application.worldData.generators.terrain.mountains.formRaster import point_in_form
from app.application.worldData.generators.terrain.mountains.sideFill import side_fill_grade_at_xy
from app.application.worldData.generators.terrain.mountains.rangeSideFill import range_side_grade_at_xy
from app.application.worldData.generators.terrain.mountains.rangeCompose import compose_range_corridor
from app.application.worldData.generators.terrain.mountains.geom import nearest_point_on_polyline_m
from app.application.worldData.generators.terrain.relief.geom.facing import uphill_facing_toward
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.planning.reliefPlan import MountainLayout
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceAspect
from app.dataModel.terrainMasks.mountain.specs import MountainSpec, MountainRangeSpec, StarForm


@dataclass(frozen=True)
class SideObservation:
    fraction: float
    aspect: SurfaceAspect
    side_kind: ReliefSideKind
    face: Facing | None


def _aspect(fraction: float, kind: ReliefSideKind, face: Facing | None) -> SideObservation:
    # A SHEER side's inner plateau is horizontal; its outer band is the face.
    horizontal = face is None or kind is ReliefSideKind.SHEER and fraction == 1.0
    return SideObservation(fraction, SurfaceAspect.HORIZONTAL if horizontal else SurfaceAspect.RELIEF_FACE,
                           kind, None if horizontal else face)


def _peak(spec: MountainSpec, x: float, y: float, span: float) -> SideObservation | None:
    geometry = construct_mountain_form(spec.form, (spec.origin_x_m, spec.origin_y_m), spec.radius_m)
    if not point_in_form(x, y, geometry, concave=isinstance(spec.form, StarForm)):
        return None
    grade = side_fill_grade_at_xy(geometry, list(spec.sides), x, y, light_span=span)
    if grade.sector_index < 0:
        return _aspect(grade.fraction, grade.kind, None)
    sector = geometry.sectors[grade.sector_index]
    # Facing is evidence of the selected side, also when the stamp has no uphill grade.
    nx, ny = sector.outward_n
    face = grade.facing or uphill_facing_toward(x, y, x - nx, y - ny)
    return _aspect(grade.fraction, grade.kind, face)


def observe_sides(layout: MountainLayout, cell: tuple[int, int], *, light_span: float) -> SideObservation | None:
    x, y = float(cell[0]), float(cell[1])
    winner: SideObservation | None = None
    for entry in layout.entries:
        if isinstance(entry, MountainRangeSpec):
            grade = range_side_grade_at_xy(x, y, spine=list(entry.spine), half_width_m=entry.width_m / 2,
                                           sides=entry.sides, light_span=light_span)
            observation = None
            if grade is not None:
                nearest = nearest_point_on_polyline_m(x, y, list(entry.spine))
                face = grade.facing or (uphill_facing_toward(x, y, *nearest) if nearest is not None else None)
                fractions, _ = compose_range_corridor(entry, [(cell, x, y)], light_span=light_span)
                observation = _aspect(fractions[cell], grade.side.kind, face)
            peaks = entry.peaks
        else:
            observation = None
            peaks = (entry,)
        for peak in peaks:
            candidate = _peak(peak, x, y, light_span)
            if candidate is not None and (observation is None or candidate.fraction > observation.fraction):
                observation = candidate
        if observation is not None and (winner is None or observation.fraction > winner.fraction):
            winner = observation
    return winner
