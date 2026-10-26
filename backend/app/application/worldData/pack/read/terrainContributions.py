"""Pack column extraction with membership metadata; no live state resolution."""

from app.dataModel.worldPack.wire.mergeMapCells import CellContribution
from app.dataModel.worldPack.wire.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire


def column_surface(column: FineTerrainColumnWire) -> tuple[int, str, str | None] | None:
    best: tuple[int, str, str | None] | None = None
    for run in column.runs:
        z_hi = max(run.z0, run.z1)
        if best is None or z_hi > best[0]:
            best = (z_hi, run.system_terrain, run.system_material)
    return best


def fine_terrain_contribution(
    chunk: FineTerrainChunkWire,
    col_lx: int,
    col_ly: int,
    x: int,
    y: int,
    z: int,
) -> CellContribution | None:
    column = next((c for c in chunk.columns if c.lx == col_lx and c.ly == col_ly), None)
    if column is None:
        return None
    for run in column.runs:
        z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
        if z_lo <= z <= z_hi:
            return CellContribution(
                x=x,
                y=y,
                z=z,
                system_terrain=run.system_terrain,
                system_material=run.system_material,
                region_uid=column.region_uid,
            )
    return None
