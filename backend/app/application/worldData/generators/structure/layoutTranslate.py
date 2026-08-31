"""Смещение StructureLayout в WORLD_LOCAL_METERS (reuse из settlement cache)."""

from dataclasses import replace

from app.application.worldData.generators.coordinates.types import MeterDelta
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)


def translate_layout(
    layout: StructureLayout,
    dx: MeterDelta | int,
    dy: MeterDelta | int,
    dz: MeterDelta | int = 0,
) -> StructureLayout:
    """Apply meter-space offset to layout coordinates (xy + z)."""
    if dx == 0 and dy == 0 and dz == 0:
        return layout

    cells = [
        replace(c, x=c.x + dx, y=c.y + dy, z=c.z + dz)
        for c in layout.cells
    ]
    rooms = [
        replace(
            r,
            map_x=(r.map_x or 0) + dx,
            map_y=(r.map_y or 0) + dy,
            map_z=(r.map_z or 0) + dz,
        )
        for r in layout.rooms
    ]
    levels = [replace(lv, z=lv.z + dz) for lv in layout.levels]
    passages = []
    for p in layout.passages:
        passages.append(replace(
            p,
            from_x=(p.from_x + dx) if p.from_x is not None else None,
            from_y=(p.from_y + dy) if p.from_y is not None else None,
            to_x=p.to_x + dx,
            to_y=p.to_y + dy,
        ))

    fp = layout.occupied_footprint
    translated_fp = None
    if fp is not None:
        translated_fp = OccupiedFootprint(
            min_x=fp.min_x + dx,
            min_y=fp.min_y + dy,
            width=fp.width,
            depth=fp.depth,
        )

    return StructureLayout(
        cells=cells,
        levels=levels,
        passages=passages,
        rooms=rooms,
        occupied_footprint=translated_fp,
    )
