"""Local climate source projection and the existing feature-detection defaults."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from pydantic.dataclasses import dataclass as validated_dataclass

from app.dataModel.climate.planning.climatePoints import AnchorSource, ClimateAnchorPoint
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


class ProminenceScale(StrEnum):
    """Caller must choose — no silent metric default."""

    METRIC = "metric"
    GRID = "grid"


@dataclass(frozen=True)
class ProminenceThresholds:
    """Min prominence for peak / basin / liquid-body detect."""

    peak: int
    basin: int
    liquid: int


@validated_dataclass(frozen=True, config=ConfigDict(extra="forbid", strict=True, revalidate_instances="always"))
class ClimateFeaturePolicy:
    synthetic_surface_terrain: TerrainKey
    water_feature_terrain: TerrainKey
    scale: ProminenceScale = ProminenceScale.METRIC
    peak_min: Annotated[StrictInt, Field(ge=0)] = 50
    basin_min: Annotated[StrictInt, Field(ge=0)] = 25
    liquid_min: Annotated[StrictInt, Field(ge=0)] = 10
    max_features: Annotated[StrictInt, Field(gt=0)] = 32
    manual_exclusion_grid: Annotated[StrictInt, Field(ge=0)] = 2


class ClimateLocalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    manual: tuple[ClimateAnchorPoint, ...]
    admin: tuple[ClimateAnchorPoint, ...]
    feature_policy: ClimateFeaturePolicy

    @model_validator(mode="after")
    def declared_sources(self) -> Self:
        if any(point.source != AnchorSource.MANUAL for point in self.manual):
            raise ValueError("manual anchors must have manual source")
        if any(point.source != AnchorSource.ADMIN for point in self.admin):
            raise ValueError("admin anchors must have admin source")
        return self
