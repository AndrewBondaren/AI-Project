"""Mountain form pipeline — FormGeometry→FormRaster→SideFill → MaskFootprint.

Light and coarse share Form/SideFill SoT; only the grid sampler differs (Q3-A).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    construct_mountain_form,
)
from app.application.worldData.generators.terrain.mountains.formRaster import (
    raster_form_footprint,
    raster_form_macro_keys,
)
from app.application.worldData.generators.terrain.mountains.rangeSideFill import (
    range_side_fill_at_points,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    side_fill_fractions,
    side_fill_fractions_at_points,
)
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_cell_center_m,
    light_to_macro_local,
    meters_to_light,
)
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSpec,
    StarForm,
)


def materialize_mountain_spec(spec: MountainSpec, scale: LightGridScale) -> MaskFootprint:
    geom = construct_mountain_form(spec.form, (spec.origin_x_m, spec.origin_y_m), spec.radius_m)
    concave = isinstance(spec.form, StarForm)
    cells = raster_form_footprint(geom, scale, concave=concave)
    fractions = side_fill_fractions(geom, spec.resolved_sides(), cells, scale)
    return MaskFootprint(cells=cells, elevation_fraction=fractions)


def materialize_mountain_range(spec: MountainRangeSpec, scale: LightGridScale) -> MaskFootprint:
    """Corridor + left/right/caps SideFill; peaks use full mountain Spec pipeline."""
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
    fractions = range_side_fill_at_points(
        spec, points, light_m=float(scale.light_m),
    )
    cells: set[LightCellRef] = set(fractions.keys())
    for peak in spec.peaks:
        peak_fp = materialize_mountain_spec(peak, scale)
        cells |= set(peak_fp.cells)
        for ref, frac in peak_fp.elevation_fraction.items():
            fractions[ref] = max(fractions.get(ref, 0.0), float(frac))
    return MaskFootprint(cells=frozenset(cells), elevation_fraction=fractions)


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
    keys = raster_form_macro_keys(geom, cell_m=cell_m, concave=concave)
    return side_fill_fractions_at_points(
        geom,
        spec.resolved_sides(),
        _coarse_macro_points(keys, cell_m=cell_m),
        light_m=float(light_m),
    )


def coarse_footprint_for_range(
    spec: MountainRangeSpec,
    *,
    cell_m: int,
    light_m: float,
) -> dict[tuple[int, int], float]:
    """Q3-A: Range SideFill sampled on macro centers; peaks overlay."""
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
    fractions = range_side_fill_at_points(
        spec,
        _coarse_macro_points(candidate_keys, cell_m=cell),
        light_m=float(light_m),
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
