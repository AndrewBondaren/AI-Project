"""Mountain form pipeline — FormGeometry→FormRaster→SideFill → MaskFootprint.

Light and coarse share Form/SideFill SoT; only the grid sampler differs (Q3-A).
Range U6 corridor+saddle lives in ``rangeCompose``; peaks max-wins here.
"""

from __future__ import annotations

import logging

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    construct_mountain_form,
)
from app.application.worldData.generators.terrain.mountains.formRaster import (
    raster_form_footprint,
    raster_form_macro_keys,
)
from app.application.worldData.generators.terrain.mountains.rangeCompose import (
    compose_range_corridor,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    side_fill_fractions_at_points,
    side_fill_grades,
)
from app.application.worldData.generators.terrain.mountains.sideGradeDecision import (
    explain_side_grade_at_xy,
    format_sides_summary,
)
from app.application.worldData.generators.terrain.relief.geom.facing import facing_wire
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_cell_center_m,
    light_to_macro_local,
    meters_to_light,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSpec,
    StarForm,
)

logger = logging.getLogger(__name__)

_GRADE_SAMPLE_LIMIT = 8


def _log_mountain_spec_grade(
    spec: MountainSpec,
    geom,
    sides: list,
    cells: frozenset[LightCellRef],
    scale: LightGridScale,
) -> None:
    """INFO sides summary + DEBUG sample: why SLOPE/SHEER and facing (tz_terrain_relief R8)."""
    logger.info(
        "relief_grade_spec | mountain origin=(%s,%s) r=%s kind=%s sides=%s cells=%d",
        spec.origin_x_m,
        spec.origin_y_m,
        spec.radius_m,
        spec.kind,
        format_sides_summary(sides),
        len(cells),
    )
    if not logger.isEnabledFor(logging.DEBUG) or not cells:
        return
    samples: list[LightCellRef] = []
    for ref in cells:
        samples.append(ref)
        if len(samples) >= _GRADE_SAMPLE_LIMIT:
            break
    for ref in samples:
        px, py = light_cell_center_m(ref.gx, ref.gy, ref.tx, ref.ty, scale)
        decision = explain_side_grade_at_xy(
            geom, sides, float(px), float(py), light_m=float(scale.light_m),
        )
        facing = facing_wire(decision.facing) or "none"
        logger.debug(
            "relief_grade_cell | mountain=(%s,%s) light=(%d,%d,%d,%d) "
            "kind=%s sector=%s t=%.3f frac=%.3f facing=%s | %s",
            spec.origin_x_m,
            spec.origin_y_m,
            ref.gx,
            ref.gy,
            ref.tx,
            ref.ty,
            decision.kind.value,
            decision.sector_index,
            decision.t,
            decision.fraction,
            facing,
            decision.reason,
        )


def _log_range_sides(spec: MountainRangeSpec) -> None:
    rs = spec.sides
    parts = [
        f"left={rs.left.kind.value}",
        f"right={rs.right.kind.value}",
    ]
    if rs.start is not None:
        parts.append(f"start={rs.start.kind.value}")
    if rs.end is not None:
        parts.append(f"end={rs.end.kind.value}")
    sheer_n = sum(
        1
        for s in (rs.left, rs.right, rs.start, rs.end)
        if s is not None and s.kind == MountainSideKind.SHEER
    )
    logger.info(
        "relief_grade_spec | range peaks=%d spine_pts=%d sides={%s} sheer_sides=%d",
        len(spec.peaks),
        len(spec.spine),
        ", ".join(parts),
        sheer_n,
    )


def materialize_mountain_spec(spec: MountainSpec, scale: LightGridScale) -> MaskFootprint:
    geom = construct_mountain_form(spec.form, (spec.origin_x_m, spec.origin_y_m), spec.radius_m)
    concave = isinstance(spec.form, StarForm)
    cells = raster_form_footprint(geom, scale, concave=concave)
    sides = spec.resolved_sides()
    grades = side_fill_grades(geom, sides, cells, scale)
    fractions = {ref: float(g.fraction) for ref, g in grades.items()}
    facing = {ref: facing_wire(g.facing) for ref, g in grades.items()}
    _log_mountain_spec_grade(spec, geom, sides, cells, scale)
    return MaskFootprint(cells=cells, elevation_fraction=fractions, system_facing=facing)


def materialize_mountain_range(spec: MountainRangeSpec, scale: LightGridScale) -> MaskFootprint:
    """U6: corridor+saddle (rangeCompose) → peaks max-wins."""
    _log_range_sides(spec)
    half = max(1, int(spec.width_m)) // 2
    xs = [p[0] for p in spec.spine]
    ys = [p[1] for p in spec.spine]
    pad = half
    lx0, ly0 = meters_to_light(min(xs) - pad, min(ys) - pad, scale)
    lx1, ly1 = meters_to_light(max(xs) + pad, max(ys) + pad, scale)
    points: list[tuple[LightCellRef, float, float]] = []
    for ly in range(ly0, ly1 + 1):
        for lx in range(lx0, lx1 + 1):
            gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
            cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
            points.append((LightCellRef(gx, gy, tx, ty), float(cx), float(cy)))
    fractions, facing = compose_range_corridor(
        spec, points, light_m=float(scale.light_m),
    )
    cells: set[LightCellRef] = set(fractions.keys())
    for peak in spec.peaks:
        peak_fp = materialize_mountain_spec(peak, scale)
        cells |= set(peak_fp.cells)
        for ref, frac in peak_fp.elevation_fraction.items():
            fractions[ref] = max(fractions.get(ref, 0.0), float(frac))
        for ref, face in peak_fp.system_facing.items():
            if face is not None:
                facing[ref] = face
    return MaskFootprint(
        cells=frozenset(cells),
        elevation_fraction=fractions,
        system_facing=facing,
    )


def materialize_mountain_entry(
    spec: MountainSpec | MountainRangeSpec,
    scale: LightGridScale,
) -> MaskFootprint:
    if isinstance(spec, MountainRangeSpec):
        return materialize_mountain_range(spec, scale)
    return materialize_mountain_spec(spec, scale)


def _coarse_macro_points(
    keys: set[tuple[int, int]],
    *,
    cell_m: int,
) -> list[tuple[tuple[int, int], float, float]]:
    cell = max(1, int(cell_m))
    half = cell // 2
    return [
        ((gx, gy), float(gx * cell + half), float(gy * cell + half))
        for gx, gy in keys
    ]


def coarse_footprint_for_spec(
    spec: MountainSpec,
    *,
    cell_m: int,
    light_m: float,
) -> dict[tuple[int, int], float]:
    """Q3-A: FormGeometry→FormRaster→SideFill on macro grid."""
    geom = construct_mountain_form(spec.form, (spec.origin_x_m, spec.origin_y_m), spec.radius_m)
    concave = isinstance(spec.form, StarForm)
    sides = spec.resolved_sides()
    logger.info(
        "relief_grade_spec | coarse mountain origin=(%s,%s) r=%s sides=%s",
        spec.origin_x_m,
        spec.origin_y_m,
        spec.radius_m,
        format_sides_summary(sides),
    )
    keys = raster_form_macro_keys(geom, cell_m=cell_m, concave=concave)
    return side_fill_fractions_at_points(
        geom,
        sides,
        _coarse_macro_points(keys, cell_m=cell_m),
        light_m=float(light_m),
    )


def coarse_footprint_for_range(
    spec: MountainRangeSpec,
    *,
    cell_m: int,
    light_m: float,
) -> dict[tuple[int, int], float]:
    """Q3-A: shared U6 corridor compose; peaks overlay."""
    _log_range_sides(spec)
    cell = max(1, int(cell_m))
    half = max(1, int(spec.width_m)) // 2
    xs = [p[0] for p in spec.spine]
    ys = [p[1] for p in spec.spine]
    pad = half
    gx0 = (min(xs) - pad) // cell
    gy0 = (min(ys) - pad) // cell
    gx1 = (max(xs) + pad) // cell
    gy1 = (max(ys) + pad) // cell
    candidate_keys = {(gx, gy) for gy in range(gy0, gy1 + 1) for gx in range(gx0, gx1 + 1)}
    points = _coarse_macro_points(candidate_keys, cell_m=cell)
    fractions, _facing = compose_range_corridor(
        spec, points, light_m=float(light_m),
    )
    for peak in spec.peaks:
        peak_fp = coarse_footprint_for_spec(peak, cell_m=cell, light_m=light_m)
        for key, frac in peak_fp.items():
            fractions[key] = max(fractions.get(key, 0.0), float(frac))
    return fractions


def coarse_footprint_for_entry(
    spec: MountainSpec | MountainRangeSpec,
    *,
    cell_m: int,
    light_m: float,
) -> dict[tuple[int, int], float]:
    """Pass 1.4 footprint + elevation fractions — same SoT as light materialize."""
    if isinstance(spec, MountainRangeSpec):
        return coarse_footprint_for_range(spec, cell_m=cell_m, light_m=light_m)
    return coarse_footprint_for_spec(spec, cell_m=cell_m, light_m=light_m)
