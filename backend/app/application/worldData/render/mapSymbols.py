"""Shared ASCII map symbols — hydrology roles + terrain keys."""

from __future__ import annotations

from collections.abc import Iterable

ROLE_SYMBOLS: dict[str, str] = {
    "coastal_sea": "~",
    "open_ocean": "≈",
    "lake": "o",
    "river_bed": "y",  # interim; `r` reserved for road
    "shore": "s",
}

TERRAIN_SYMBOLS: dict[str, str] = {
    "liquid_body": "~",
    "plains": ".",
    "forest": "f",
    "shore": "s",
    "urban": "u",
    "road": "r",
    "ravine": "v",
    "mountain": "m",
}

# Unknown terrain/role: blank cell — never first-letter of key (collides: ravine→r, road→r).
UNKNOWN_SYMBOL = " "

LOCATION_PIN_SYMBOL = "@"

# Missing height cell: spaces of the same width as numeric cells (caller sets width).
HEIGHT_MISSING_FILL = " "


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
