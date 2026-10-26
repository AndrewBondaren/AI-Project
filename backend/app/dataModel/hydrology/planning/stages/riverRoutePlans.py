"""Accepted routes, occupancy claims and retained pre-river fine samples."""

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute, fine_order, require_map
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ, SurfaceGridCoord


S = TypeVar("S", SurfaceGridCoord, FineXY)


def _coordinate_order(cell: SurfaceGridCoord | FineXY) -> tuple[int, ...]:
    if isinstance(cell, SurfaceGridCoord):
        return cell.gy, cell.gx
    return fine_order(cell)


class RiverRouteBatch(BaseModel, Generic[S]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    routes: tuple[RiverRoute[S], ...]
    claims: tuple[tuple[S, MapCellHydrology], ...]

    @model_validator(mode="after")
    def consistent_claims(self) -> Self:
        require_map(self.claims, _coordinate_order)
        if len({route.river_uid for route in self.routes}) != len(self.routes):
            raise ValueError("duplicate river UID in route batch")
        coordinates = [cell for route in self.routes for segment in route.segments for cell in segment.path]
        coordinates.extend(cell for cell, _ in self.claims)
        if len({isinstance(cell, SurfaceGridCoord) for cell in coordinates}) > 1:
            raise ValueError("route batch cannot mix coarse and fine coordinate spaces")
        # Route/segment order is significant: shared classifier boundaries keep
        # the same last-published metadata as the existing claims producer.
        expected = {cell: (route.river_uid, segment.edge_uid, route.drainage)
                    for route in self.routes for segment in route.segments for cell in segment.path
                    if cell != route.receiver_cell}
        if {cell for cell, _ in self.claims} != set(expected):
            raise ValueError("claims must cover exactly the accepted river beds")
        for cell, claim in self.claims:
            uid, edge_uid, drainage = expected[cell]
            if (claim.role is not HydrologyCellRole.RIVER_BED or claim.water_body_uid != uid
                    or claim.connection_edge_uid != edge_uid or claim.river_drainage != drainage):
                raise ValueError("claim identity, edge and drainage must match the accepted route")
        return self


CoarseRiverPlan = RiverRouteBatch[SurfaceGridCoord]


class FineRiverPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    routes: tuple[RiverRoute[FineXY], ...]
    base_surface_z: tuple[tuple[FineXY, FineZ], ...]

    @model_validator(mode="after")
    def sampled_routes(self) -> Self:
        require_map(self.base_surface_z, fine_order)
        if len({route.river_uid for route in self.routes}) != len(self.routes):
            raise ValueError("duplicate river UID in fine plan")
        sampled = {cell for cell, _ in self.base_surface_z}
        if any(cell not in sampled for route in self.routes for segment in route.segments for cell in segment.path):
            raise ValueError("fine routes require pre-river samples including each receiver")
        return self
