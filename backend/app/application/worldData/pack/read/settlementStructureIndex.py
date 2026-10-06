"""Index authored outdoor shell cells from settlement.zst — raster + city ASCII."""

from __future__ import annotations

from app.dataModel.worldPack.settlementStructureWire import (
    BuildingShellWire,
    SettlementStructureWire,
    ShellCellWire,
)
from app.application.worldData.pack.io.packBlobWire import InteriorTransitionsRebuildRequired
from app.dataModel.locations.transitions.transition import Transition


def building_with_interior_transitions(wire: SettlementStructureWire, building_uid: str) -> BuildingShellWire:
    for district in wire.districts:
        for area in district.areas:
            for building in area.buildings:
                if building.location_uid == building_uid:
                    if building.interior_transitions is None:
                        raise InteriorTransitionsRebuildRequired(f"building {building_uid!r} requires interior transition pack rebuild")
                    return building
    raise KeyError(building_uid)


def transitions_for_level(building: BuildingShellWire, level_uid: str) -> list[Transition]:
    if building.interior_transitions is None:
        raise InteriorTransitionsRebuildRequired(f"building {building.location_uid!r} requires interior transition pack rebuild")
    return [item for item in building.interior_transitions.transitions
            if item.source.level_uid == level_uid or item.destination.level_uid == level_uid]


def index_shell_cells(wire: SettlementStructureWire) -> dict[tuple[int, int, int], ShellCellWire]:
    """World (x, y, z) → last shell cell. Last write wins on collision."""
    index: dict[tuple[int, int, int], ShellCellWire] = {}

    def put_all(cells: list[ShellCellWire]) -> None:
        for cell in cells:
            index[(cell.x, cell.y, cell.z)] = cell

    put_all(list(wire.barrier_cells))
    for district in wire.districts:
        put_all(list(district.barrier_cells))
        for area in district.areas:
            put_all(list(area.yard_cells))
            put_all(list(area.barrier_cells))
            for small in area.small_layouts:
                put_all(list(small))
            for building in area.buildings:
                put_all(list(building.shell_cells))
    return index
