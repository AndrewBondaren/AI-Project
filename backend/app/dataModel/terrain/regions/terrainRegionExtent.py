"""Generation area, distinct from placement original_area (GEO-1 §6.3)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.identity.uid import EntityUid


class TerrainRegionModel(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")


class RegionExtentIssueCode(StrEnum):
    MISSING_REGION = "TERRAIN_REGION_MISSING"
    IDENTITY_MISMATCH = "TERRAIN_REGION_IDENTITY_MISMATCH"
    MISSING_ANCHOR = "TERRAIN_REGION_ANCHOR_MISSING"
    INVALID_GEOMETRY = "TERRAIN_REGION_INVALID_GEOMETRY"


class TerrainRegionExtent(TerrainRegionModel, frozen=True):
    region_uid: EntityUid
    generation_area_fine2: StrictInt = Field(ge=0)
