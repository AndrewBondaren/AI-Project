"""C8 outdoor shell filter — reads StructureElement.OUTDOOR_SHELL_ELEMENTS."""

from __future__ import annotations

from app.dataModel.structure.enums.buildingElement import (
    OUTDOOR_SHELL_ELEMENTS,
    StructureElement,
)
from app.dataModel.worldPack.settlementStructureWire import ShellCellWire
from app.db.models.mapCell import MapCell


def _element(cell: MapCell) -> StructureElement | None:
    raw = cell.system_building_element
    if not raw:
        return None
    try:
        return StructureElement(raw)
    except ValueError:
        return None


def is_outdoor_shell_cell(cell: MapCell) -> bool:
    el = _element(cell)
    return el is not None and el in OUTDOOR_SHELL_ELEMENTS


def map_cell_to_shell_wire(cell: MapCell) -> ShellCellWire:
    return ShellCellWire(
        x=cell.x,
        y=cell.y,
        z=cell.z,
        system_terrain=cell.system_terrain,
        system_material=cell.system_material,
        system_building_element=cell.system_building_element,
        is_structural=cell.is_structural,
        location_uid=cell.location_uid,
        system_facing=cell.system_facing,
    )


def outdoor_shell_wires(cells: list[MapCell]) -> list[ShellCellWire]:
    return [map_cell_to_shell_wire(c) for c in cells if is_outdoor_shell_cell(c)]


def cells_to_shell_wires(cells: list[MapCell]) -> list[ShellCellWire]:
    """Yard / barrier — persist as-is (C9), no C8 filter."""
    return [map_cell_to_shell_wire(c) for c in cells]
