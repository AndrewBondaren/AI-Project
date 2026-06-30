"""
Debug endpoints — только для разработки и тестирования.
Не должны использоваться в production flow.
"""
from dataclasses import asdict
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureGeneratorService,
)
from app.application.worldData.generators.structure.gridRenderer import render_all_levels, FACING_ARROW
from app.application.worldData.generators.utils.facing import Facing
from app.db.models.namedLocation import NamedLocation
from datetime import datetime, timezone


class _LogCapture(logging.Handler):
    """Перехватывает записи во время генерации для возврата в debug-ответе."""

    def __init__(self, level: int = logging.WARNING) -> None:
        super().__init__(level)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))

router = APIRouter(prefix="/debug", tags=["debug"])

_structure_generator = StructureGeneratorService()


@router.post("/worlds/{world_uid}/generate-structure")
async def debug_generate_structure(
    world_uid: str,
    map_x: int = 0,
    map_y: int = 0,
    map_z: int = 0,
    wall_material: str = "stone",
    floor_material: str = "wood",
    verbose: bool = False,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    """
    Генерирует структуру здания из шаблона и возвращает layout.

    Принимает JSON-шаблон через file upload или path к файлу.
    Мир берётся из БД по world_uid.
    Здание создаётся как временный объект с переданными координатами.

    Возвращает: cells, levels, passages, rooms + сводка по элементам.
    """
    template = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(template, dict):
        raise HTTPException(status_code=422, detail="Template must be a JSON object")

    world = await container.world_service().get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    building = NamedLocation(
        location_uid=f"debug-building-{world_uid}",
        world_uid=world_uid,
        display_name="[Debug] " + template.get("display_name", "Building"),
        system_location_type="building",
        created_at=datetime.now(timezone.utc).isoformat(),
        map_x=map_x,
        map_y=map_y,
        map_z=map_z,
        parent_wall_material=wall_material,
        parent_floor_material=floor_material,
    )

    log_level = logging.DEBUG if verbose else logging.WARNING
    capture = _LogCapture(level=log_level)
    gen_logger = logging.getLogger("app.application.worldData.generators")
    gen_logger.addHandler(capture)
    try:
        layout = _structure_generator.generate_from_template(world, building, template)
    finally:
        gen_logger.removeHandler(capture)

    from collections import Counter
    element_counts = Counter(c.system_building_element for c in layout.cells)

    levels_by_uid = {lvl.level_uid: lvl.z for lvl in layout.levels}
    cells_by_xyz  = {(c.x, c.y, c.z): c for c in layout.cells}
    markers: dict[tuple[int, int, int], str] = {}
    for p in layout.passages:
        if p.system_passage_type == "staircase":
            tz = levels_by_uid.get(p.to_level_uid)
            if tz is not None:
                markers[(p.to_x, p.to_y, tz)] = "$"
            fz = levels_by_uid.get(p.from_level_uid)
            if fz is not None:
                cell = cells_by_xyz.get((p.from_x, p.from_y, fz))
                if cell and cell.system_facing:
                    markers[(p.from_x, p.from_y, fz)] = FACING_ARROW.get(Facing(cell.system_facing), "@")
    grids = render_all_levels(layout.cells, markers=markers)

    return JSONResponse({
        "summary": {
            "levels":   len(layout.levels),
            "rooms":    len(layout.rooms),
            "cells":    len(layout.cells),
            "passages": len(layout.passages),
            "elements": dict(element_counts),
        },
        "validation": {
            "warnings": capture.records,
            "count":    len(capture.records),
        },
        "levels": [
            {
                "level_uid":    lvl.level_uid,
                "z":            lvl.z,
                "z_height":     lvl.z_height,
                "display_name": lvl.display_name,
                "isolated":     lvl.isolated,
            }
            for lvl in sorted(layout.levels, key=lambda l: l.z)
        ],
        "rooms": [
            {
                "location_uid":            r.location_uid,
                "display_name":            r.display_name,
                "system_location_subtype": r.system_location_subtype,
                "origin":                  {"x": r.map_x, "y": r.map_y, "z": r.map_z},
                "is_public":               r.is_public,
                "is_forbidden":            r.is_forbidden,
            }
            for r in layout.rooms
        ],
        "passages": [
            {
                "passage_uid":        p.passage_uid,
                "system_passage_type": p.system_passage_type,
                "from_level_uid":     p.from_level_uid,
                "from_xy":            [p.from_x, p.from_y],
                "to_level_uid":       p.to_level_uid,
                "to_xy":              [p.to_x, p.to_y],
                "is_bidirectional":   p.is_bidirectional,
            }
            for p in layout.passages
        ],
        "grids": {str(z): grid for z, grid in grids.items()},
        "cells": [
            {
                "x": c.x, "y": c.y, "z": c.z,
                "element":    c.system_building_element,
                "material":   c.system_material,
                "structural": c.is_structural,
                "facing":     c.system_facing,
                "railing":    c.railing_sides if hasattr(c, "railing_sides") else None,
            }
            for c in layout.cells
        ],
    })
