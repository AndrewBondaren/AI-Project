"""Shared ASCII map symbols — hydrology roles + terrain keys."""

from __future__ import annotations

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
}

LOCATION_PIN_SYMBOL = "@"


def symbol_for_role_or_terrain(
    *,
    hydrology_role: str | None = None,
    system_terrain: str | None = None,
) -> str:
    if hydrology_role:
        return ROLE_SYMBOLS.get(str(hydrology_role), str(hydrology_role)[0])
    if system_terrain:
        return TERRAIN_SYMBOLS.get(str(system_terrain), str(system_terrain)[0])
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
    lines.append("?=unknown")
    return "\n".join(lines)
