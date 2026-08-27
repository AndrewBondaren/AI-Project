"""L2 outdoor grade ASCII — one 3×3 cell (center + 8 slots).

SoT: ``docs/tz_terrain_relief_consume.md``. Pack slots only. Dump does not
invent ``+`` from ``surface_z`` and does not call ``opposite``. Does not read
column ``system_facing``. Glyphs: ``grade_slot_glyph`` (production) /
``grade_ray_glyph`` (legacy ``GradeRimRay`` tests).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.application.worldData.render.gridAxes import (
    format_grid_header,
    format_y_gutter,
)
from app.application.worldData.render.mapSymbols import (
    GRADE_CELL_INNER_WIDTH,
    format_glyph_field,
    grade_ray_glyph,
    grade_slot_glyph,
    join_height_row,
)
from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_COUNT,
    GradeCellSlots,
    GradeCouple,
    GradeOctant,
    GradeSeam,
    facing_from_octant,
)


class GradeRayIndex:
    """Outgoing rays keyed by cell. Last-wins on ``(cell, Facing)``."""

    def __init__(self, rays: Iterable[GradeRimRay] = ()) -> None:
        self._by_cell: dict[tuple[int, int], dict[Facing, ReliefSideKind]] = {}
        for ray in rays:
            self.add(ray)

    def add(self, ray: GradeRimRay) -> None:
        cell = ray.cell
        slots = self._by_cell.get(cell)
        if slots is None:
            slots = {}
            self._by_cell[cell] = slots
        slots[ray.facing] = ray.kind

    def rays_at(self, xy: tuple[int, int]) -> Mapping[Facing, ReliefSideKind]:
        return self._by_cell.get(xy, {})

    def has_any(self) -> bool:
        return bool(self._by_cell)

    def cells(self) -> Iterable[tuple[int, int]]:
        return self._by_cell.keys()

    def relative_to(self, origin_x: int, origin_y: int) -> GradeRayIndex:
        """World XY → local keys (subtract origin)."""
        ox, oy = int(origin_x), int(origin_y)
        return GradeRayIndex(
            GradeRimRay(
                x=ray.x - ox,
                y=ray.y - oy,
                facing=ray.facing,
                kind=ray.kind,
            )
            for ray in self.iter_rays()
        )

    def iter_rays(self) -> Iterable[GradeRimRay]:
        for (x, y), slots in self._by_cell.items():
            for facing, kind in slots.items():
                yield GradeRimRay(x=x, y=y, facing=facing, kind=kind)

    def restricted_to(self, cells: Iterable[tuple[int, int]]) -> GradeRayIndex:
        allowed = set(cells)
        return GradeRayIndex(ray for ray in self.iter_rays() if ray.cell in allowed)

    def without_couple(self) -> GradeRayIndex:
        """``grade_{n}`` slices omit COUPLE (walls would be a solid plus)."""
        return GradeRayIndex(
            ray for ray in self.iter_rays() if ray.kind is not ReliefSideKind.COUPLE
        )


class GradeSlotIndex:
    """Sidecar ``slots[8]`` keyed by cell. Glyphs from codes, not edge Facing."""

    def __init__(self, cells: Iterable[GradeCellSlots] = ()) -> None:
        self._by_cell: dict[tuple[int, int], tuple[int | None, ...]] = {}
        for cell in cells:
            self._by_cell[cell.cell] = tuple(int(code) for code in cell.slots)

    def _with_rows(
        self,
        rows: dict[tuple[int, int], tuple[int | None, ...]],
    ) -> GradeSlotIndex:
        out = GradeSlotIndex()
        out._by_cell = rows
        return out

    def slots_at(self, xy: tuple[int, int]) -> tuple[int | None, ...] | None:
        return self._by_cell.get((int(xy[0]), int(xy[1])))

    def has_any(self) -> bool:
        return bool(self._by_cell)

    def cells(self) -> Iterable[tuple[int, int]]:
        return self._by_cell.keys()

    def relative_to(self, origin_x: int, origin_y: int) -> GradeSlotIndex:
        ox, oy = int(origin_x), int(origin_y)
        return self._with_rows({
            (x - ox, y - oy): slots
            for (x, y), slots in self._by_cell.items()
        })

    def restricted_to(self, cells: Iterable[tuple[int, int]]) -> GradeSlotIndex:
        allowed = {(int(x), int(y)) for x, y in cells}
        return self._with_rows({
            xy: slots for xy, slots in self._by_cell.items() if xy in allowed
        })

    def without_couple(self) -> GradeSlotIndex:
        """``grade_{n}`` slices: Octant/SHEER only (consume: no COUPLE wall)."""
        couple = int(GradeCouple.COUPLE)
        seam = int(GradeSeam.SEAM)
        rows: dict[tuple[int, int], tuple[int | None, ...]] = {}
        for xy, slots in self._by_cell.items():
            mapped = tuple(
                None if code is None or int(code) in {couple, seam} else int(code)
                for code in slots
            )
            if any(code is not None for code in mapped):
                rows[xy] = mapped
        return self._with_rows(rows)


def pick_grade_consume_index(
    *,
    slot_index: GradeSlotIndex | None,
    ray_index: GradeRayIndex | None,
    origin_x: int,
    origin_y: int,
) -> GradeRayIndex | GradeSlotIndex:
    """Prefer sidecar slots. Empty slots → legacy ``GradeRimRay`` (unit tests)."""
    slots = (slot_index or GradeSlotIndex()).relative_to(origin_x, origin_y)
    if slots.has_any():
        return slots
    return (ray_index or GradeRayIndex()).relative_to(origin_x, origin_y)


def facing_cell_slot(facing: Facing) -> tuple[int, int]:
    """3×3 ``(row, col)`` for outward ``Facing``. North (+y) is row 0; center is (1,1)."""
    dx, dy = GRID_OUTWARD_DELTA[facing]
    return (1 - dy, 1 + dx)


def compose_grade_cell(
    center: str,
    rays: Mapping[Facing, ReliefSideKind],
) -> tuple[str, str, str]:
    """Three 3-glyph rows (N strip, mid, S strip). Glyphs come only from pack kinds."""
    grid = [[" ", " ", " "] for _ in range(GRADE_CELL_INNER_WIDTH)]
    glyph = center[:1] if center else " "
    grid[1][1] = glyph if glyph else " "
    for facing, kind in rays.items():
        row, col = facing_cell_slot(facing)
        if row == 1 and col == 1:
            continue
        grid[row][col] = grade_ray_glyph(kind, facing)
    return ("".join(grid[0]), "".join(grid[1]), "".join(grid[2]))


def compose_grade_cell_from_slots(
    center: str,
    slots: Sequence[int | None] | None,
) -> tuple[str, str, str]:
    """Three 3-glyph rows. Glyph from code at dump-edge position. No ``opposite``."""
    grid = [[" ", " ", " "] for _ in range(GRADE_CELL_INNER_WIDTH)]
    glyph = center[:1] if center else " "
    grid[1][1] = glyph if glyph else " "
    if not slots:
        return ("".join(grid[0]), "".join(grid[1]), "".join(grid[2]))
    for position in range(GRADE_SLOT_COUNT):
        if position >= len(slots):
            break
        code = slots[position]
        if code is None:
            continue
        row, col = facing_cell_slot(facing_from_octant(GradeOctant(position)))
        if row == 1 and col == 1:
            continue
        grid[row][col] = grade_slot_glyph(int(code))
    return ("".join(grid[0]), "".join(grid[1]), "".join(grid[2]))


def draw_grade_ray_grid(
    centers: Mapping[tuple[int, int], str],
    rays: GradeRayIndex | GradeSlotIndex,
    *,
    title: str,
    width: int,
    extra_headers: list[str] | None = None,
    coord_prefix: str = "",
    bounds: tuple[int, int, int, int] | None = None,
) -> str:
    """3 text rows per gy; field W + space-separated cells — same pitch as ``surface_z``.

    Slots are pack kinds only. COUPLE ``+`` is read from the sidecar, not from z.
    """
    if bounds is not None:
        x0, x1, y0, y1 = bounds
    elif centers:
        xs = [x for x, _ in centers]
        ys = [y for _, y in centers]
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
    field_w = max(GRADE_CELL_INNER_WIDTH, int(width))
    for y in range(y1, y0 - 1, -1):
        bands = ([], [], [])
        for x in range(x0, x1 + 1):
            key = (x, y)
            if isinstance(rays, GradeSlotIndex):
                top, mid, bot = compose_grade_cell_from_slots(
                    centers.get(key, " "),
                    rays.slots_at(key),
                )
            else:
                top, mid, bot = compose_grade_cell(
                    centers.get(key, " "),
                    rays.rays_at(key),
                )
            bands[0].append(format_glyph_field(top, width=field_w))
            bands[1].append(format_glyph_field(mid, width=field_w))
            bands[2].append(format_glyph_field(bot, width=field_w))
        lines.append(f"{format_y_gutter(None)}{join_height_row(bands[0])}|")
        lines.append(f"{format_y_gutter(y)}{join_height_row(bands[1])}|")
        lines.append(f"{format_y_gutter(None)}{join_height_row(bands[2])}|")
    return "\n".join(lines)
