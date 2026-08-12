"""Convert MapCell columns to FineTerrainChunkWire."""

from __future__ import annotations

from app.dataModel.spatial.facing import Facing, parse_facing
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


def _surface_cell(cells: list[MapCell]) -> MapCell | None:
    """Highest-z cell in column (= surface after columnFill stamp — PAR-G9 / PAR-T-1)."""
    if not cells:
        return None
    return max(cells, key=lambda c: c.z)


def _column_surface_attrs(cells: list[MapCell]) -> tuple[Facing | None, str | None]:
    """Facing + grade_uid from surface cell only (PAR-T-1 / PAR-T-4)."""
    top = _surface_cell(cells)
    if top is None:
        return None, None
    try:
        facing = parse_facing(top.system_facing)
    except ValueError:
        facing = None
    uid = str(top.system_grade_uid) if top.system_grade_uid else None
    return facing, uid


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
    columns: list[FineTerrainColumnWire] = []
    for (lx, ly), col_cells in sorted(by_column.items()):
        facing, grade_uid = _column_surface_attrs(col_cells)
        columns.append(
            FineTerrainColumnWire(
                lx=lx,
                ly=ly,
                runs=_compress_z_runs(col_cells),
                system_facing=facing,
                system_grade_uid=grade_uid,
            ),
        )
    return FineTerrainChunkWire(cx=cx, cy=cy, chunk_columns=chunk_columns, columns=columns)
