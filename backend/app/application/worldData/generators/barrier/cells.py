"""Emit outdoor barrier map_cells."""

from __future__ import annotations

from app.db.models.mapCell import MapCell
from app.db.models.world import World


def emit_barrier_cells(
    world:        World,
    ring:         set[tuple[int, int]],
    gate_coords:  set[tuple[int, int]],
    material:     str,
    location_uid: str,
    ground_z:     int,
) -> list[MapCell]:
    cells: list[MapCell] = []
    for x, y in sorted(ring):
        cells.append(MapCell(
            world_uid=world.world_uid,
            x=x,
            y=y,
            z=ground_z,
            system_terrain="gate" if (x, y) in gate_coords else "wall",
            system_material=material,
            is_structural=True,
            location_uid=location_uid,
        ))
    return cells
