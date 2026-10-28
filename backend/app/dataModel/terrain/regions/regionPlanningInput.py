"""Complete captured geometry for pre-water region measurement (GEO-1 §6.29-M)."""

from typing import Self

from pydantic import field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import RegionShape
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionModel
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


class RegionGeometryInput(TerrainRegionModel, frozen=True):
    region_uid: EntityUid
    geometry: RegionShape | RegionCoverage
    owner_ref: PlanRef | None = None

    @field_validator("geometry", mode="before")
    @classmethod
    def revalidate_geometry(cls, value: object) -> object:
        return PlacementIntent.validate_existing_shape(value)

    @model_validator(mode="after")
    def coverage_owner(self) -> Self:
        if isinstance(self.geometry, RegionCoverage):
            if self.geometry.region_uid != self.region_uid:
                raise ValueError("claim coverage identity must match region identity")
            if self.owner_ref is None:
                raise ValueError("claim coverage requires owner plan ref")
        elif self.owner_ref is not None:
            raise ValueError("authored shape has no claim owner ref")
        return self


class TerrainRegionPlanningInput(TerrainRegionModel, frozen=True):
    declared_world_bounds: WorldBounds | None
    topology: WorldTopology
    grid: SurfaceGridSettings
    regions: tuple[RegionGeometryInput, ...]
    anchors: tuple[WaterAnchorInput, ...]

    @field_validator("topology", mode="before")
    @classmethod
    def revalidate_topology(cls, value: object) -> object:
        return WorldTopology.model_validate(value.model_dump(warnings=False), strict=True) if isinstance(value, WorldTopology) else value

    @field_validator("declared_world_bounds", mode="before")
    @classmethod
    def revalidate_bounds(cls, value: object) -> object:
        return WorldBounds.model_validate(value.model_dump(warnings=False), strict=True) if isinstance(value, WorldBounds) else value

    @model_validator(mode="after")
    def unique_inputs(self) -> Self:
        if len({r.region_uid for r in self.regions}) != len(self.regions):
            raise ValueError("duplicate input region UID")
        if len({a.source_uid for a in self.anchors}) != len(self.anchors):
            raise ValueError("duplicate anchor UID")
        if self.declared_world_bounds is not None:
            normalized = WorldTopology(mode=self.topology.mode, bounds=self.declared_world_bounds).bounds
            if normalized != self.topology.bounds:
                raise ValueError("declared world bounds do not match resolved topology")
        return self
