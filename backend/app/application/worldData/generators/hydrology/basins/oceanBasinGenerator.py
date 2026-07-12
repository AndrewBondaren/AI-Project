"""Open ocean expansion from coastal sea ring — D HY-2 scope OPEN_OCEAN."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def expand_open_ocean(
    heightmap: SurfaceHeightmap,
    coastal_by_cell: dict[tuple[int, int], MapCellHydrology],
    *,
    z_sea: int | None = None,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    """
  v1 declare path: relabel coastal_sea mass → OPEN_OCEAN at z_sea (no map-wide flood).
    """
    level = resolve_z_sea(None) if z_sea is None else z_sea
    coastal_cells = {
        cell
        for cell, entry in coastal_by_cell.items()
        if entry.role == HydrologyCellRole.COASTAL_SEA
    }
    if not coastal_cells:
        return {}, None

    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []

    for cell in coastal_cells:
        heightmap.surface_z[cell] = level
        by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
        xs.extend([cell[0], cell[0]])
        ys.extend([cell[1], cell[1]])

    dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return by_cell, dirty


def generate_open_ocean(
    heightmap: SurfaceHeightmap,
    coastal_by_cell: dict[tuple[int, int], MapCellHydrology],
    *,
    z_sea: int | None = None,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    return expand_open_ocean(heightmap, coastal_by_cell, z_sea=z_sea)
