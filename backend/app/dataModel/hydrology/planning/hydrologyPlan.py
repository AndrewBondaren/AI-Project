"""Frozen declared geometry, accepted routes, and final hydrology output facts."""

from collections.abc import Callable
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, TypeAdapter, field_validator, model_validator

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineDelta, FineXY, FineZ, SurfaceGridCoord
from app.dataModel.worldPack.wire.hydrologyMaskWire import HydrologyMaskWire


class LakePaint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    location_uid: EntityUid | None
    shoreline_segments: tuple[tuple[FineXY, FineXY], ...]


class CoastlinePaint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    location_uid: EntityUid | None
    segments: tuple[tuple[FineXY, FineXY], ...]


class SegmentRiverPaint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    edge_uid: EntityUid
    location_uid: EntityUid | None
    segment: tuple[FineXY, FineXY]
    width_fine: FineDelta = Field(strict=True, gt=0)


class IntentRiverPaint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    river_uid: EntityUid
    path: tuple[FineXY, ...] = Field(min_length=2)
    width_wire: StrictInt

    @field_validator("width_wire")
    @classmethod
    def valid_wire_width(cls, value: int) -> int:
        if HydrologyMaskWire(width=value).width != value:
            raise ValueError("intent width must already satisfy HydrologyMaskWire bounds")
        return value


class DeclaredWaterPaint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    lakes: tuple[LakePaint, ...]
    coastlines: tuple[CoastlinePaint, ...]
    segments: tuple[SegmentRiverPaint, ...]
    intents: tuple[IntentRiverPaint, ...]


S = TypeVar("S")


class RiverPathSegment(BaseModel, Generic[S]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    path: tuple[S, ...] = Field(min_length=1)
    connection_type: HydrologyConnectionType
    edge_uid: EntityUid | None
    location_uid: EntityUid | None
    declared: StrictBool

    @model_validator(mode="after")
    def river_connection(self) -> Self:
        if self.connection_type not in (HydrologyConnectionType.RIVER, HydrologyConnectionType.MOUNTAIN_RIVER):
            raise ValueError("river segment requires a river connection type")
        return self


class RiverRoute(BaseModel, Generic[S]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    river_uid: EntityUid
    segments: tuple[RiverPathSegment[S], ...] = Field(min_length=1)
    receiver_cell: S
    drainage: RiverDrainageLink

    @model_validator(mode="after")
    def confirmed_receiver(self) -> Self:
        path = tuple(cell for segment in self.segments for cell in segment.path)
        if not path or path[-1] != self.receiver_cell:
            raise ValueError("route receiver must be terminal")
        if not any(cell != self.receiver_cell for cell in path):
            raise ValueError("route requires at least one land-bed cell")
        if self.receiver_cell in path[:-1]:
            raise ValueError("route receiver may only occur at the terminal cell")
        if self.drainage.river_uid != self.river_uid:
            raise ValueError("route/drainage river UID mismatch")
        TypeAdapter[EntityUid](EntityUid).validate_python(self.drainage.receiver_uid)
        if self.drainage.receiver_uid == self.river_uid:
            raise ValueError("river cannot drain into itself")
        return self


def require_map[K, V](rows: tuple[tuple[K, V], ...], order: Callable[[K], tuple[int, ...]]) -> None:
    coords = tuple(cell for cell, _ in rows)
    if len(set(coords)) != len(coords):
        raise ValueError("duplicate hydrology coordinate")
    if coords != tuple(sorted(coords, key=order)):
        raise ValueError("hydrology coordinates require canonical order")


def coarse_order(cell: SurfaceGridCoord) -> tuple[int, ...]:
    return cell.gy, cell.gx


def fine_order(cell: FineXY) -> tuple[int, ...]:
    return cell[1], cell[0]


def require_unique_water(bodies: tuple[WaterBody, ...], unions: tuple[PhysicalWaterUnion, ...]) -> set[str]:
    body_ids = {body.water_body_uid for body in bodies}
    union_ids = {union.water_system_uid for union in unions}
    if len(body_ids) != len(bodies) or len(union_ids) != len(unions):
        raise ValueError("duplicate physical water identity")
    return body_ids | union_ids


def require_rooted_links(links: dict[str, str], roots: set[str]) -> None:
    if roots.intersection(links):
        raise ValueError("river identity collides with physical water identity")
    for origin in links:
        seen: set[str] = set()
        uid = origin
        while uid not in roots:
            if uid in seen:
                raise ValueError("drainage cycle")
            seen.add(uid)
            receiver = links.get(uid)
            if receiver is None:
                raise ValueError("drainage chain has no known water root")
            uid = receiver


class HydrologyRoutesPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
    water_bodies: tuple[WaterBody, ...]
    physical_unions: tuple[PhysicalWaterUnion, ...]
    coarse_routes: tuple[RiverRoute[SurfaceGridCoord], ...]
    fine_routes: tuple[RiverRoute[FineXY], ...]
    fine_base_surface_z: tuple[tuple[FineXY, FineZ], ...]
    declared_paint: DeclaredWaterPaint

    @model_validator(mode="after")
    def proven_routes(self) -> Self:
        require_map(self.coarse_open_water, coarse_order)
        require_map(self.fine_base_surface_z, fine_order)
        roots = require_unique_water(self.water_bodies, self.physical_unions)
        coarse_links = {route.river_uid: route.drainage.receiver_uid for route in self.coarse_routes}
        fine_links = {route.river_uid: route.drainage.receiver_uid for route in self.fine_routes}
        if len(coarse_links) != len(self.coarse_routes) or len(fine_links) != len(self.fine_routes):
            raise ValueError("duplicate river UID in coordinate space")
        body_kinds = {body.water_body_uid: body.kind for body in self.water_bodies}
        for route in (*self.coarse_routes, *self.fine_routes):
            if route.drainage.receiver_uid in roots:
                if not isinstance(route.drainage.receiver_kind, BasinKind):
                    raise ValueError("physical water receiver requires basin kind")
                kind = body_kinds.get(route.drainage.receiver_uid)
                if kind is not None and route.drainage.receiver_kind != kind:
                    raise ValueError("drainage receiver kind disagrees with accepted water body")
        require_rooted_links(coarse_links, roots)
        require_rooted_links(coarse_links | fine_links, roots)
        fine_cells = {cell for cell, _ in self.fine_base_surface_z}
        for route in self.fine_routes:
            if any(cell not in fine_cells for segment in route.segments for cell in segment.path):
                raise ValueError("fine route requires sampled pre-river heights including receiver")
        return self


class HydrologyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coarse_surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]
    coarse_hydro: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
    sparse_fine_hydro: tuple[tuple[FineXY, MapCellHydrology], ...]
    fine_z_overrides: tuple[tuple[FineXY, FineZ], ...]
    water_bodies: tuple[WaterBody, ...]
    physical_unions: tuple[PhysicalWaterUnion, ...]
    declared_paint: DeclaredWaterPaint

    @model_validator(mode="after")
    def consistent_facts(self) -> Self:
        require_map(self.coarse_surface_z, coarse_order)
        require_map(self.coarse_hydro, coarse_order)
        require_map(self.sparse_fine_hydro, fine_order)
        require_map(self.fine_z_overrides, fine_order)
        require_unique_water(self.water_bodies, self.physical_unions)
        surface = {cell for cell, _ in self.coarse_surface_z}
        if any(cell not in surface for cell, _ in self.coarse_hydro):
            raise ValueError("coarse hydrology outside final surface")
        return self
