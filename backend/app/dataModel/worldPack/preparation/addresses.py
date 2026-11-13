"""Immutable logical payload addresses shared by Pack preparation and storage."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDatasetKind


class _PackAddress(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class PackMapTileAddress(_PackAddress):
    kind: Literal["map_tile"]
    gx: int
    gy: int


class PackChunkAddress(_PackAddress):
    kind: Literal["wilderness_chunk"]
    gx: int
    gy: int
    cx: int = Field(ge=0)
    cy: int = Field(ge=0)


class PackLocationTerrainAddress(_PackAddress):
    kind: Literal["location_terrain"]
    location_uid: EntityUid


class PackSettlementAddress(_PackAddress):
    kind: Literal["settlement"]
    location_uid: EntityUid


class PackCoarseClimateAddress(_PackAddress):
    kind: Literal["climate_coarse"]


class PackFineClimateAddress(_PackAddress):
    kind: Literal["climate_fine"]
    gx: int
    gy: int


class PackLocationsIndexAddress(_PackAddress):
    kind: Literal["locations_index"]


class PackSpatialRootAddress(_PackAddress):
    kind: Literal["spatial_root"]
    domain: SpatialDatasetKind


class PackTileGradeSlotsAddress(_PackAddress):
    kind: Literal["tile_grade_slots"]
    gx: int
    gy: int


class PackLocationGradeSlotsAddress(_PackAddress):
    kind: Literal["location_grade_slots"]
    location_uid: EntityUid


PackPartAddress = Annotated[
    PackMapTileAddress | PackChunkAddress | PackLocationTerrainAddress
    | PackSettlementAddress | PackCoarseClimateAddress | PackFineClimateAddress
    | PackLocationsIndexAddress | PackSpatialRootAddress | PackTileGradeSlotsAddress
    | PackLocationGradeSlotsAddress,
    Field(discriminator="kind"),
]
