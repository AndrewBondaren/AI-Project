"""Convert MapCell columns to FineTerrainChunkWire."""

from __future__ import annotations

from collections import Counter

from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun
from app.db.models.mapCell import MapCell


def _compress_z_runs(cells: list[MapCell]) -> list[FineTerrainZRun]:
    if not cells:
        return []
    ordered = sorted(cells, key=lambda c: c.z)
    runs: list[FineTerrainZRun] = []
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
            FineTerrainZRun(
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
        FineTerrainZRun(
            z0=z_start,
            z1=cur_z,
            system_terrain=cur_terrain,
            system_material=cur_material,
        ),
    )
    return runs


def _column_system_facing(cells: list[MapCell]) -> str | None:
    """Column-level facing: majority of non-null MapCell.system_facing (surface first)."""
    votes = [c.system_facing for c in cells if c.system_facing]
    if not votes:
        return None
    # Prefer top-z cell if it has facing.
    top = max(cells, key=lambda c: c.z)
    if top.system_facing:
        return top.system_facing
    return Counter(votes).most_common(1)[0][0]


def cells_to_fine_terrain_chunk(
    cx: int,
    cy: int,
    chunk_columns: int,
    origin_x: int,
    origin_y: int,
    cells: list[MapCell],
) -> FineTerrainChunkWire:
    by_column: dict[tuple[int, int], list[MapCell]] = {}
    for cell in cells:
        lx = cell.x - origin_x
        ly = cell.y - origin_y
        by_column.setdefault((lx, ly), []).append(cell)
    columns = [
        FineTerrainColumnWire(
            lx=lx,
            ly=ly,
            runs=_compress_z_runs(col_cells),
            system_facing=_column_system_facing(col_cells),
        )
        for (lx, ly), col_cells in sorted(by_column.items())
    ]
    return FineTerrainChunkWire(cx=cx, cy=cy, chunk_columns=chunk_columns, columns=columns)
