"""Convert MapCell columns to L2ChunkWire."""

from __future__ import annotations

from app.dataModel.worldPack.l2ChunkWire import L2ChunkWire, L2ColumnWire, L2ZRun
from app.db.models.mapCell import MapCell


def _compress_z_runs(cells: list[MapCell]) -> list[L2ZRun]:
    if not cells:
        return []
    ordered = sorted(cells, key=lambda c: c.z)
    runs: list[L2ZRun] = []
    cur_z = ordered[0].z
    cur_terrain = ordered[0].system_terrain or ""
    cur_material = ordered[0].system_material
    z_start = cur_z
    for cell in ordered[1:]:
        terrain = cell.system_terrain or ""
        if terrain == cur_terrain and cell.system_material == cur_material and cell.z == cur_z + 1:
            cur_z = cell.z
            continue
        runs.append(
            L2ZRun(
                z0=z_start,
                z1=cur_z,
                system_terrain=cur_terrain,
                system_material=cur_material,
            ),
        )
        z_start = cell.z
        cur_z = cell.z
        cur_terrain = terrain
        cur_material = cell.system_material
    runs.append(
        L2ZRun(
            z0=z_start,
            z1=cur_z,
            system_terrain=cur_terrain,
            system_material=cur_material,
        ),
    )
    return runs


def cells_to_l2_chunk(
    cx: int,
    cy: int,
    chunk_columns: int,
    origin_x: int,
    origin_y: int,
    cells: list[MapCell],
) -> L2ChunkWire:
    by_column: dict[tuple[int, int], list[MapCell]] = {}
    for cell in cells:
        lx = cell.x - origin_x
        ly = cell.y - origin_y
        by_column.setdefault((lx, ly), []).append(cell)
    columns = [
        L2ColumnWire(lx=lx, ly=ly, runs=_compress_z_runs(col_cells))
        for (lx, ly), col_cells in sorted(by_column.items())
    ]
    return L2ChunkWire(cx=cx, cy=cy, chunk_columns=chunk_columns, columns=columns)
