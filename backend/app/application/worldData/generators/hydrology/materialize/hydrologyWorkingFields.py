"""One coarse projection and indexed fine outputs per hydrology request."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Self

from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import Coord


def _tile_index[T](rows: Mapping[Coord, T], span: int) -> Mapping[Coord, Mapping[Coord, T]]:
    grouped: dict[Coord, dict[Coord, T]] = {}
    for coord, value in rows.items():
        tile = (coord[0] // span, coord[1] // span)
        grouped.setdefault(tile, {})[coord] = value
    return MappingProxyType({tile: MappingProxyType(values) for tile, values in grouped.items()})


@dataclass(frozen=True, slots=True)
class HydrologyWorkingFields:
    coarse_hydro: Mapping[Coord, MapCellHydrology]
    coarse_surface_z: Mapping[Coord, int]
    fine_z_overrides: Mapping[Coord, int]
    sparse_fine_hydro: Mapping[Coord, MapCellHydrology]
    _fine_z: Mapping[Coord, Mapping[Coord, int]] = field(repr=False)
    _fine_hydro: Mapping[Coord, Mapping[Coord, MapCellHydrology]] = field(repr=False)
    _empty_z: Mapping[Coord, int] = field(repr=False)
    _empty_hydro: Mapping[Coord, MapCellHydrology] = field(repr=False)

    @classmethod
    def from_plan(cls, plan: HydrologyPlan, grid: SurfaceGridSettings) -> Self:
        fine_z: Mapping[Coord, int] = MappingProxyType({(x, y): z for (x, y), z in plan.fine_z_overrides})
        fine_hydro: Mapping[Coord, MapCellHydrology] = MappingProxyType(
            {(x, y): value for (x, y), value in plan.sparse_fine_hydro})
        return cls(
            MappingProxyType({(cell.gx, cell.gy): value for cell, value in plan.coarse_hydro}),
            MappingProxyType({(cell.gx, cell.gy): z for cell, z in plan.coarse_surface_z}),
            fine_z, fine_hydro,
            _tile_index(fine_z, grid.fine_span),
            _tile_index(fine_hydro, grid.fine_span),
            MappingProxyType({}), MappingProxyType({}))

    def fine_z_for_tile(self, gx: GridX, gy: GridY) -> Mapping[Coord, int]:
        return self._fine_z.get((gx, gy), self._empty_z)

    def fine_hydro_for_tile(self, gx: GridX, gy: GridY) -> Mapping[Coord, MapCellHydrology]:
        return self._fine_hydro.get((gx, gy), self._empty_hydro)
