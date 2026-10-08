"""Root POJO for `worlds.hydrology`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, validate_declared_rivers_topology
from app.dataModel.hydrology.landforms import HydrologyLandformsPolicy
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.annotationPolicy import DefaultWhenMissing


class WorldHydrology(BaseModel):
    """Root POJO for `worlds.hydrology`."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-HYDROLOGY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultWhenMissing[bool] = True
    default_shore: DefaultWhenMissing[HydrologyShoreDefaults] = Field(default_factory=HydrologyShoreDefaults)
    default_rivers: DefaultWhenMissing[HydrologyRiversPolicy] = Field(default_factory=HydrologyRiversPolicy)
    default_lakes: DefaultWhenMissing[HydrologyLakesPolicy] = Field(default_factory=HydrologyLakesPolicy)
    default_seas: DefaultWhenMissing[HydrologySeasPolicy] = Field(default_factory=HydrologySeasPolicy)
    default_landforms: DefaultWhenMissing[HydrologyLandformsPolicy] = Field(
        default_factory=HydrologyLandformsPolicy,
    )
    materialize_named_locations: DefaultWhenMissing[bool] = False
    declared_lakes: DefaultWhenMissing[list[DeclaredLake]] = Field(default_factory=list)
    declared_coastlines: DefaultWhenMissing[list[DeclaredCoastline]] = Field(default_factory=list)
    declared_rivers: DefaultWhenMissing[list[DeclaredRiver]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_river_systems(self) -> WorldHydrology:
        validate_declared_rivers_topology(self.declared_rivers)
        return self

    @classmethod
    def canonical_empty(cls) -> WorldHydrology:
        """Full explicit blob after normalize (equivalent to missing `{}`)."""
        return cls()
