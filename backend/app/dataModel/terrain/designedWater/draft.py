"""Strategy results before common placement preparation; no procedural footprints."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSourceKind
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.fields.field import ContinentalField
from app.dataModel.terrain.relief.bathymetry.floorProfile import (
    BasinFloorProfile, FieldFloorProfile, SampledFloorProfile,
)
from app.dataModel.topology.worldTopology import Coord


class WaterDesignDraftKind(StrEnum):
    AUTHORED = "authored"
    PROCEDURAL = "procedural"


class _WaterDesignDraft(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    metadata: WaterSourceMetadata
    floor_z: Annotated[FineZ, Field(strict=True)]

    @model_validator(mode="after")
    def floor_below_water(self) -> Self:
        if self.floor_z >= self.metadata.level:
            raise ValueError("floor_z must be below water level")
        return self


class AuthoredWaterDesignDraft(_WaterDesignDraft, frozen=True):
    kind: Literal[WaterDesignDraftKind.AUTHORED] = WaterDesignDraftKind.AUTHORED
    footprints: tuple[frozenset[Coord], ...]
    coordinate_space: CoordinateSpace
    floor_profile: BasinFloorProfile | None

    @model_validator(mode="after")
    def complete_profile(self) -> Self:
        if self.metadata.source_kind is WaterDesignSourceKind.PROCEDURAL:
            raise ValueError("authored draft requires authored source metadata")
        if self.coordinate_space is CoordinateSpace.LOCATION_FINE_GRID:
            raise ValueError("water draft requires world coordinates")
        if not self.footprints or any(not footprint for footprint in self.footprints):
            raise ValueError("authored draft requires nonempty footprints")
        profile = self.floor_profile
        if isinstance(profile, SampledFloorProfile):
            coords = frozenset(c for footprint in self.footprints for c in footprint)
            if profile.space != self.coordinate_space or frozenset(c for c, _ in profile.samples) != coords:
                raise ValueError("sampled floor must cover the footprints in the same space")
            if any(z >= self.metadata.level for _, z in profile.samples):
                raise ValueError("sampled floors must be below water level")
            if self.floor_z != min(z for _, z in profile.samples):
                raise ValueError("floor_z must be the minimum sampled floor")
        elif isinstance(profile, FieldFloorProfile):
            if profile.level != self.metadata.level or self.floor_z != max(profile.z_min, profile.level - profile.depth):
                raise ValueError("field floor bounds must match metadata and floor_z")
        return self


class ProceduralWaterDesignDraft(_WaterDesignDraft, frozen=True):
    kind: Literal[WaterDesignDraftKind.PROCEDURAL] = WaterDesignDraftKind.PROCEDURAL
    field: ContinentalField
    floor_profile: FieldFloorProfile

    @model_validator(mode="after")
    def matching_field_floor(self) -> Self:
        if self.metadata.source_kind is not WaterDesignSourceKind.PROCEDURAL:
            raise ValueError("procedural draft requires procedural source metadata")
        profile = self.floor_profile
        if profile.recipe != self.field.recipe or profile.level != self.metadata.level:
            raise ValueError("field floor must use the same recipe and water level")
        if self.floor_z != max(profile.z_min, profile.level - profile.depth):
            raise ValueError("floor_z must match field floor bounds")
        return self


type WaterDesignDraft = Annotated[
    AuthoredWaterDesignDraft | ProceduralWaterDesignDraft, Field(discriminator="kind"),
]
