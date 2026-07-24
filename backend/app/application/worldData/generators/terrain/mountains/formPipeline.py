"""Mountain form pipeline — FormGeometry→FormRaster→SideFill → MaskFootprint.

Formerly ``materialize.py`` (Q10: avoid clash with ``materializer.py``).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    construct_mountain_form,
)
from app.application.worldData.generators.terrain.mountains.formRaster import (
    raster_form_footprint,
)
from app.application.worldData.generators.terrain.mountains.geom import (
    dist_point_to_polyline_m,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    side_fill_fractions,
)
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.rasterDisk import raster_disk
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
    """INTERIM corridor (Q12): distance-to-spine falloff — not full Range SideFill left/right/caps.

    Target: lateral SideFill per § Mountain Range. Peaks use full mountain Spec pipeline.
    """
    half = max(1, int(spec.width_m) // 2)
    xs = [p[0] for p in spec.spine]
    ys = [p[1] for p in spec.spine]
    pad = half
    lx0, ly0 = meters_to_light(min(xs) - pad, min(ys) - pad, scale)
    lx1, ly1 = meters_to_light(max(xs) + pad, max(ys) + pad, scale)
    cells: set[LightCellRef] = set()
    fractions: dict[LightCellRef, float] = {}
    half_f = float(half)
    for ly in range(ly0, ly1 + 1):
        for lx in range(lx0, lx1 + 1):
            gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
            cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
            d = dist_point_to_polyline_m(float(cx), float(cy), list(spec.spine))
            if d > half_f:
                continue
            ref = LightCellRef(gx, gy, tx, ty)
            cells.add(ref)
            fractions[ref] = max(0.0, 1.0 - d / half_f)
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


def coarse_disk_keys_for_spec(
    spec: MountainSpec,
    *,
    cell_m: int,
) -> set[tuple[int, int]]:
    """INTERIM Pass 1.4: macro-grid **disk** from ``radius_m`` (not FormRaster).

    L0 light bake uses FormGeometry→FormRaster→SideFill on the same Spec.
    Footprints intentionally differ until Q3-A (unify coarse to Spec→FormRaster).
    See tz_map_light_bake § Open questions Q3 / tech debt.
    """
    cx = int(spec.origin_x_m) // max(1, cell_m)
    cy = int(spec.origin_y_m) // max(1, cell_m)
    radius_cells = max(0, int(round(int(spec.radius_m) / max(1, cell_m))))
    return raster_disk(cx, cy, radius_cells)
