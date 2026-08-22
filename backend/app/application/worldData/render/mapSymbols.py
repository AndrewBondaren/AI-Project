"""Shared ASCII map symbols — hydrology roles + terrain keys + relief facing."""

from __future__ import annotations

from collections.abc import Iterable

from app.application.worldData.facingArrows import FACING_ARROW
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind

ROLE_SYMBOLS: dict[str, str] = {
    "coastal_sea": "~",
    "open_ocean": "≈",
    "lake": "o",
    "river_bed": "y",  # interim; `r` reserved for road
    "shore": "s",
}

TERRAIN_SYMBOLS: dict[str, str] = {
    "liquid_body": "~",
    "plains": "_",  # flat ground; `.` reserved for building floor
    "earth": "_",  # ordinary dirt / default material landcover if painted as terrain
    "forest": "f",
    "shore": "s",
    "shore_river": "s",
    "shore_mountain_river": "s",
    "shore_lake": "s",
    "shore_sea": "s",
    "urban": "u",
    "road": "r",
    "ravine": "v",
    "mountain": "m",
}

# Grade cell without facing (SHEER) — vertical face, not a compass.
GRADE_SHEER_SYMBOL = "┃"
GRADE_COUPLE_SYMBOL = "+"
GRADE_EMPTY_SYMBOL = " "

# Unknown terrain/role: blank cell — never first-letter of key (collides: ravine→r, road→r).
UNKNOWN_SYMBOL = " "

LOCATION_PIN_SYMBOL = "@"

# Missing height cell: spaces of the same width as numeric cells (caller sets width).
HEIGHT_MISSING_FILL = " "


# 3×3 grade cell inner width (tz_terrain_relief_consume).
GRADE_CELL_INNER_WIDTH = 3


def paired_height_cell_width(zs: Iterable[int]) -> int:
    """``surface_z`` + grade-ray dump share this W (max of height pad and 3)."""
    return max(height_cell_width(zs), GRADE_CELL_INNER_WIDTH)


def format_glyph_field(token: str, *, width: int) -> str:
    """Right-align a 3-glyph 3×3 row in the same field as ``format_height_cell``."""
    w = max(GRADE_CELL_INNER_WIDTH, int(width))
    return f"{token:>{w}s}"


def height_token(surface_z: int) -> str:
    """Decimal ``surface_z`` string (may be multi-char, including leading ``-``)."""
    return str(int(surface_z))


def height_cell_width(zs: Iterable[int]) -> int:
    """Pad width = longest token in the set (at least 1)."""
    width = 1
    for z in zs:
        width = max(width, len(height_token(z)))
    return width


def format_height_cell(surface_z: int | None, *, width: int) -> str:
    """Right-align ``z`` in a fixed field; ``None`` → blank field of ``width``."""
    w = max(1, int(width))
    if surface_z is None:
        return HEIGHT_MISSING_FILL * w
    return f"{int(surface_z):>{w}d}"


def join_height_row(cells: Iterable[str]) -> str:
    """Space-separated fixed-width cells — columns stay aligned across rows."""
    return " ".join(cells)


def symbol_for_role_or_terrain(
    *,
    hydrology_role: str | None = None,
    system_terrain: str | None = None,
) -> str:
    if hydrology_role:
        return ROLE_SYMBOLS.get(str(hydrology_role), UNKNOWN_SYMBOL)
    if system_terrain:
        return TERRAIN_SYMBOLS.get(str(system_terrain), UNKNOWN_SYMBOL)
    return "?"


def render_map_legend(*, mark_location: bool = False, pin_label: str | None = None) -> str:
    role_part = " ".join(f"{sym}={name}" for name, sym in ROLE_SYMBOLS.items())
    terrain_part = " ".join(f"{sym}={name}" for name, sym in TERRAIN_SYMBOLS.items())
    lines = [
        f"hydrology: {role_part}",
        f"terrain: {terrain_part}",
    ]
    if mark_location:
        lines.append(
            f"binding: {LOCATION_PIN_SYMBOL}={pin_label or 'location pin'}",
        )
    lines.append("(space)=unmapped  ?=missing cell")
    return "\n".join(lines)


def render_height_legend(
    *,
    z_min: int | None = None,
    z_max: int | None = None,
    z_hist: dict[int, int] | None = None,
    cell_width: int | None = None,
) -> str:
    lines = [
        "height: each cell = decimal surface_z; field width = max(len(str(z))) in grid; "
        "right-aligned; cells space-separated; blank field = missing",
    ]
    if cell_width is not None:
        lines.append(f"cell_width={cell_width}")
    if z_min is not None and z_max is not None:
        lines.append(f"range: z_min={z_min} z_max={z_max}")
    if z_hist:
        parts = " ".join(f"{z}×{n}" for z, n in sorted(z_hist.items()))
        lines.append(f"hist: {parts}")
    return "\n".join(lines)


def facing_arrow(facing: Facing | str | None) -> str | None:
    """Unicode arrow for ``Facing``; ``None`` if missing/unknown."""
    if facing is None:
        return None
    try:
        key = facing if isinstance(facing, Facing) else Facing(str(facing))
    except ValueError:
        return None
    return FACING_ARROW.get(key)


def grade_ray_glyph(kind: ReliefSideKind, facing: Facing) -> str:
    """Edge slot for one outgoing ray — SLOPE arrow, SHEER bar."""
    if kind is ReliefSideKind.SHEER:
        return GRADE_SHEER_SYMBOL
    arrow = facing_arrow(facing)
    return arrow if arrow is not None else GRADE_SHEER_SYMBOL


def grade_symbol(
    *,
    system_grade_uid: str | None,
    system_facing: Facing | str | None,
) -> str:
    """Relief overlay cell: arrow (SLOPE uphill) | sheer bar | blank if not in grade."""
    if not system_grade_uid:
        return GRADE_EMPTY_SYMBOL
    arrow = facing_arrow(system_facing)
    if arrow is not None:
        return arrow
    return GRADE_SHEER_SYMBOL


def render_grade_legend() -> str:
    parts = " ".join(f"{sym}={f.value}" for f, sym in FACING_ARROW.items())
    return (
        f"grade 3x3: center=surface; edges=outgoing rim rays "
        f"(SLOPE {parts}; {GRADE_SHEER_SYMBOL}=sheer; "
        f"{GRADE_COUPLE_SYMBOL}=unified surface); "
        f"empty edge=missing leftover; not occupancy overlay"
    )
