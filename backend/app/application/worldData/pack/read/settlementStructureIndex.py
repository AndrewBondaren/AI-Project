"""Index authored outdoor shell cells from settlement.zst — raster + city ASCII."""

from __future__ import annotations

from app.dataModel.worldPack.settlementStructureWire import (
    SettlementStructureWire,
    ShellCellWire,
)


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
