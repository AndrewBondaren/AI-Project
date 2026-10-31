"""Bounded natural windows from ready geometry, without preparation or hill selection."""
from bisect import bisect_left, bisect_right

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.hills.hillLayout import materialize_hills
from app.application.worldData.generators.terrain.passes.lightSurfaceRefine import refine_light_surface
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ, LightCellRef
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainTile, PreparedNaturalTerrain
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


def _light_key(cell: LightCellRef) -> tuple[int, int, int, int]:
    return cell.gy, cell.gx, cell.ty, cell.tx


def _natural_z(prepared: PreparedNaturalTerrain, gx: int, gy: int, tx: int, ty: int) -> int:
    light = prepared.light
    key = (gy, gx, ty, tx)
    i = bisect_left(light.base_surface_z, key, key=lambda row: _light_key(row[0]))
    if i == len(light.base_surface_z) or _light_key(light.base_surface_z[i][0]) != key:
        raise ValueError("missing prepared natural light sample")
    z = light.base_surface_z[i][1]
    m = bisect_left(light.mountain_cells, key, key=lambda e: _light_key(e.cell))
    if m < len(light.mountain_cells) and _light_key(light.mountain_cells[m].cell) == key:
        z = light.mountain_cells[m].surface_z
    r = bisect_left(light.ravine_cells, key, key=lambda e: _light_key(e.cell))
    if r < len(light.ravine_cells) and _light_key(light.ravine_cells[r].cell) == key:
        z = light.ravine_cells[r].surface_z
    return z


def _tile(prepared: PreparedNaturalTerrain, gx: int, gy: int) -> NaturalTerrainTile:
    i = bisect_left(prepared.tiles, (gy, gx), key=lambda t: (t.gy, t.gx))
    if i == len(prepared.tiles) or (prepared.tiles[i].gy, prepared.tiles[i].gx) != (gy, gx):
        raise ValueError("window outside prepared natural tile extent")
    return prepared.tiles[i]


def _protected(tile: NaturalTerrainTile, x: int, y: int) -> bool:
    i = bisect_right(tile.protected_spans, (y, x), key=lambda s: (s.y, s.x0))-1
    return i >= 0 and tile.protected_spans[i].y == y and x < tile.protected_spans[i].x1


class NaturalWindowJob:
    def materialize(self, prepared: PreparedNaturalTerrain, cells: RegionCoverage,
                    control: PlanBuildControl) -> FineSurfaceWindow:
        control.raise_if_shutdown()
        cells = RegionCoverage.model_validate(cells)
        if not cells.spans:
            raise ValueError("natural window requires nonempty coverage")
        bounds = prepared.topology.bounds
        if any(not bounds.contains(s.x0, s.y) or not bounds.contains(s.x1-1, s.y) for s in cells.spans):
            raise ValueError("natural window requires canonical coverage within prepared topology")
        base = prepared.base
        span = base.grid.fine_span
        rows = []
        protected = set()
        for row in cells.spans:
            x = row.x0
            while x < row.x1:
                control.raise_if_shutdown()
                gx, gy = x//span, row.y//span
                stop = min(row.x1, (gx+1)*span)
                tile = _tile(prepared, gx, gy)
                surface = refine_light_surface(gx, gy, base.grid,
                    lambda tx, ty: _natural_z(prepared, gx, gy, tx, ty), seed=base.seed,
                    z_min=base.z_min, z_max=base.z_max, policy=prepared.refine_policy,
                    local_cells=((px-gx*span, row.y-gy*span) for px in range(x, stop)))
                materialize_hills(surface, tile.hills, GridBBox(x, stop-1, row.y, row.y),
                                  z_min=base.z_min, z_max=base.z_max)
                for px in range(x, stop):
                    coordinate = (FineX(px), FineY(row.y))
                    rows.append((coordinate, FineZ(surface[coordinate])))
                    if _protected(tile, px, row.y):
                        protected.add(coordinate)
                x = stop
        control.raise_if_shutdown()
        return FineSurfaceWindow(coverage=cells, surface_z=tuple(rows),
            protected_cells=frozenset(protected), topology=prepared.topology)
