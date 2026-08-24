"""Shared FineTerrain column → ASCII symbols / grid draw (L2 location + wilderness).

Pure kernel: no pack I/O, no location_uid / tile gx knowledge.
Adapters supply title, headers, and column key space.

Diagnostics (expose L2 heightfield / thin-column gaps vs building-like walls):
- ``surface_z`` — per-cell max world-z (FineTerrain top)
- ``column_span`` — how many world-z the column occupies (1 ≈ only top / thin band)
- ``cliff_delta`` — max |Δz_top| vs 4-neighbors (large = face should exist; often empty in pack)
- dense ``z_occupied`` slices — every z covered by a run (not only endpoints)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.application.worldData.render.gridAxes import (
    format_grid_header,
    format_x_axis_ruler,
    format_y_gutter,
)
from app.application.worldData.render.gradeRayDump import (
    GradeRayIndex,
    draw_grade_ray_grid,
)
from app.application.worldData.render.mapSymbols import (
    format_height_cell,
    height_cell_width,
    join_height_row,
    paired_height_cell_width,
    symbol_for_role_or_terrain,
)
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainColumnWire, FineTerrainZRun

# 4-neighborhood for cliff-face Δz (tile-local / local keys).
_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def run_covers(run: FineTerrainZRun, z: int) -> bool:
    z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
    return z_lo <= z <= z_hi


def terrain_at_z(col: FineTerrainColumnWire, z: int) -> str | None:
    for run in col.runs:
        if run_covers(run, z):
            return run.system_terrain
    return None


def top_terrain(col: FineTerrainColumnWire) -> tuple[int, str] | None:
    """Highest world-z sample in column → (z, system_terrain)."""
    best: tuple[int, str] | None = None
    for run in col.runs:
        z_hi = max(run.z0, run.z1)
        if best is None or z_hi > best[0]:
            best = (z_hi, run.system_terrain)
    return best


def column_z_bounds(col: FineTerrainColumnWire) -> tuple[int, int] | None:
    """Inclusive (z_lo, z_hi) over all runs, or None if empty."""
    if not col.runs:
        return None
    z_lo = min(min(r.z0, r.z1) for r in col.runs)
    z_hi = max(max(r.z0, r.z1) for r in col.runs)
    return z_lo, z_hi


def column_span(col: FineTerrainColumnWire) -> int:
    """Occupied world-z count (inclusive bounds). 1 ≈ surface-only / thin band."""
    bounds = column_z_bounds(col)
    if bounds is None:
        return 0
    z_lo, z_hi = bounds
    return int(z_hi - z_lo + 1)


def z_endpoints(columns: Iterable[FineTerrainColumnWire]) -> list[int]:
    """Distinct run endpoints (not every integer in thick bands)."""
    zs: set[int] = set()
    for col in columns:
        for run in col.runs:
            zs.add(min(run.z0, run.z1))
            zs.add(max(run.z0, run.z1))
    return sorted(zs)


def z_occupied(columns: Iterable[FineTerrainColumnWire]) -> list[int]:
    """Every world-z covered by at least one run (dense; exposes mid-band of walls)."""
    zs: set[int] = set()
    for col in columns:
        for run in col.runs:
            z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
            zs.update(range(z_lo, z_hi + 1))
    return sorted(zs)


def symbols_surface_top(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for key, col in cols.items():
        top = top_terrain(col)
        if top is not None:
            out[key] = symbol_for_role_or_terrain(system_terrain=top[1])
    return out


def columns_have_grade_uid(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> bool:
    return any(col.system_grade_uid for col in cols.values())


def paired_width_from_columns(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> int:
    return paired_height_cell_width(values_surface_z(cols).values())


def should_dump_grade(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    rays: GradeRayIndex,
) -> bool:
    """Write ``surface_grade`` if leftover rays or any uid (consume TZ)."""
    return rays.has_any() or columns_have_grade_uid(cols)


def _keys_at_surface_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    z: int,
) -> set[tuple[int, int]]:
    want = int(z)
    return {xy for xy, sz in values_surface_z(cols).items() if int(sz) == want}


def crop_bounds_around_keys(
    keys: Iterable[tuple[int, int]],
    mosaic: tuple[int, int, int, int],
    *,
    halo: int = 1,
) -> tuple[int, int, int, int] | None:
    """Inclusive bbox of ``keys`` expanded by ``halo``, clamped to mosaic."""
    cells = list(keys)
    if not cells:
        return None
    mx0, mx1, my0, my1 = mosaic
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    return (
        max(mx0, min(xs) - halo),
        min(mx1, max(xs) + halo),
        max(my0, min(ys) - halo),
        min(my1, max(ys) + halo),
    )


def should_dump_grade_at_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    rays: GradeRayIndex,
    z: int,
) -> bool:
    keys = _keys_at_surface_z(cols, z)
    if any(cols[xy].system_grade_uid for xy in keys if xy in cols):
        return True
    leftover = rays.without_couple()
    return any(xy in keys for xy in leftover.cells())


def draw_grade_consume_grid(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    rays: GradeRayIndex,
    *,
    title: str,
    extra_headers: list[str] | None = None,
    coord_prefix: str = "",
    bounds: tuple[int, int, int, int] | None = None,
    surface_z: int | None = None,
) -> str:
    """Single L2 grade dump: 3×3 consume cell. ``surface_z`` filters PAR-G9."""
    if surface_z is None:
        if not should_dump_grade(cols, rays):
            return ""
        centers = symbols_surface_top(cols)
        view = rays
    else:
        if not should_dump_grade_at_z(cols, rays, surface_z):
            return ""
        keys = _keys_at_surface_z(cols, surface_z)
        material = symbols_at_z(cols, surface_z)
        centers = {xy: material[xy] for xy in keys if xy in material}
        view = rays.restricted_to(keys).without_couple()
    if bounds is None and cols:
        xs = [x for x, _ in cols]
        ys = [y for _, y in cols]
        bounds = (min(xs), max(xs), min(ys), max(ys))
    return draw_grade_ray_grid(
        centers,
        view,
        title=title,
        width=paired_width_from_columns(cols),
        extra_headers=extra_headers,
        coord_prefix=coord_prefix,
        bounds=bounds,
    )


def grade_consume_z_levels(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    rays: GradeRayIndex,
) -> list[int]:
    """World-z values that have uid or a rim ray on that surface."""
    zs = values_surface_z(cols)
    out: set[int] = set()
    for xy, col in cols.items():
        if col.system_grade_uid and xy in zs:
            out.add(int(zs[xy]))
    for xy in rays.without_couple().cells():
        if xy in zs:
            out.add(int(zs[xy]))
    return sorted(out)


def symbols_at_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    z: int,
) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for key, col in cols.items():
        terrain = terrain_at_z(col, z)
        if terrain is not None:
            out[key] = symbol_for_role_or_terrain(system_terrain=terrain)
    return out


def symbols_by_occupied_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[int, dict[tuple[int, int], str]]:
    """Single-pass: world-z → cells present in FineTerrain runs (dump / dense slices).

    Prefer this over calling ``symbols_at_z`` once per occupied z — mountain tiles
    can have thousands of z; per-z full scans are O(Z·columns).
    """
    out: dict[int, dict[tuple[int, int], str]] = {}
    for key, col in cols.items():
        for run in col.runs:
            sym = symbol_for_role_or_terrain(system_terrain=run.system_terrain)
            z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
            for z in range(z_lo, z_hi + 1):
                bucket = out.get(z)
                if bucket is None:
                    bucket = {}
                    out[z] = bucket
                bucket[key] = sym
    return out


def values_surface_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[tuple[int, int], int]:
    """Per-column highest world-z (FineTerrain top / surface_z)."""
    out: dict[tuple[int, int], int] = {}
    for key, col in cols.items():
        top = top_terrain(col)
        if top is not None:
            out[key] = int(top[0])
    return out


def values_column_span(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[tuple[int, int], int]:
    """Per-column occupied z-count (diagnostic)."""
    return {key: column_span(col) for key, col in cols.items() if col.runs}


def values_cliff_delta(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[tuple[int, int], int]:
    """Max |Δz_top| vs 4-neighbors. Large value + span≈1 ⇒ missing vertical face cells."""
    tops = values_surface_z(cols)
    out: dict[tuple[int, int], int] = {}
    for (x, y), z_top in tops.items():
        best = 0
        for dx, dy in _NEIGHBORS:
            nz = tops.get((x + dx, y + dy))
            if nz is None:
                continue
            best = max(best, abs(int(z_top) - int(nz)))
        out[(x, y)] = best
    return out


def column_diagnostics_summary(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> str:
    """One-line smoke: thick columns vs steep neighbors with thin fill."""
    spans = values_column_span(cols)
    deltas = values_cliff_delta(cols)
    n = len(spans)
    thick = sum(1 for s in spans.values() if s > 1)
    steep = sum(1 for d in deltas.values() if d >= 2)
    # Steep neighbor jump but column only 1 z thick → classic heightfield wall gap.
    gap_suspect = 0
    for key, span in spans.items():
        if span <= 1 and deltas.get(key, 0) >= 2:
            gap_suspect += 1
    return (
        f"column_diag: n={n} span>1={thick} cliff_delta>=2={steep} "
        f"thin_steep_gap_suspect={gap_suspect} "
        f"(suspect = span<=1 and neighbor |Δz_top|>=2; walls like buildings need mid-z cells)"
    )


def draw_symbol_grid(
    symbols: dict[tuple[int, int], str],
    *,
    title: str,
    extra_headers: list[str] | None = None,
    coord_prefix: str = "",
    bounds: tuple[int, int, int, int] | None = None,
) -> str:
    """Draw ASCII from (x,y)→symbol. Missing cells → space (aligned frame).

    ``bounds=(x0,x1,y0,y1)`` fixes the frame (use mosaic / max extent so every
    z-slice shares the same axes and does not shift when sparse).
    Without bounds, frame is the content bbox of ``symbols``.
    """
    if bounds is not None:
        x0, x1, y0, y1 = bounds
    elif symbols:
        xs = [x for x, _ in symbols]
        ys = [y for _, y in symbols]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
    else:
        return ""
    if x1 < x0 or y1 < y0:
        return ""
    lines = [title]
    if extra_headers:
        lines.extend(extra_headers)
    lines.append(format_grid_header(x0, x1, y0, y1, cell_size_m=1, prefix=coord_prefix))
    lines.extend(format_x_axis_ruler(x0, x1))
    for y in range(y1, y0 - 1, -1):
        row = "".join(symbols.get((x, y), " ") for x in range(x0, x1 + 1))
        lines.append(f"{format_y_gutter(y)}{row}|")
    lines.extend(format_x_axis_ruler(x0, x1))
    return "\n".join(lines)


def format_sparse_symbol_cells(
    symbols: dict[tuple[int, int], str],
    *,
    title: str,
    extra_headers: list[str] | None = None,
) -> str:
    """Compact dump format: one ``x\\ty\\tsymbol`` line per present cell.

    Prefer for detailed_bake ``z/<n>.txt`` when heightfield contours have a huge
    empty bbox (full ASCII would be mostly spaces × thousands of z).
    """
    if not symbols:
        return ""
    xs = [x for x, _ in symbols]
    ys = [y for _, y in symbols]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    lines = [
        title,
        (
            f"format=sparse_xy  cells={len(symbols)}  "
            f"bbox=x{x0}..{x1},y{y0}..{y1}"
        ),
    ]
    if extra_headers:
        lines.extend(extra_headers)
    lines.append("x\ty\tsymbol")
    for x, y in sorted(symbols.keys(), key=lambda k: (-k[1], k[0])):
        lines.append(f"{x}\t{y}\t{symbols[(x, y)]}")
    return "\n".join(lines)


def draw_int_grid(
    values: dict[tuple[int, int], int],
    *,
    title: str,
    extra_headers: list[str] | None = None,
    coord_prefix: str = "",
    width: int | None = None,
) -> str:
    """Fixed-width decimal grid (same pad rules as L0 ``ascii_height``)."""
    if not values:
        return ""
    xs = [x for x, _ in values]
    ys = [y for _, y in values]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    field_w = int(width) if width is not None else height_cell_width(values.values())
    lines = [title]
    if extra_headers:
        lines.extend(extra_headers)
    lines.append(format_grid_header(x0, x1, y0, y1, cell_size_m=1, prefix=coord_prefix))
    for y in range(y1, y0 - 1, -1):
        cells = [
            format_height_cell(values.get((x, y)), width=field_w)
            for x in range(x0, x1 + 1)
        ]
        lines.append(f"{format_y_gutter(y)}{join_height_row(cells)}|")
    return "\n".join(lines)
