"""One coherent region snapshot and its matching coverage plan (GEO-1 §6.29-M)."""

from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent, TerrainRegionModel


class TerrainRegionsSnapshot(TerrainRegionModel, frozen=True):
    world_uid: EntityUid
    snapshot_uid: EntityUid
    world_region: TerrainRegionExtent | None
    regions: tuple[TerrainRegionExtent, ...]

    @model_validator(mode="after")
    def unique_regions(self) -> Self:
        entries = self.all_regions()
        if len({r.region_uid for r in entries}) != len(entries):
            raise ValueError("duplicate region UID in snapshot")
        if self.world_region is not None and self.world_region.generation_area_fine2 == 0:
            raise ValueError("existing world region must have positive area")
        return self

    def all_regions(self) -> tuple[TerrainRegionExtent, ...]:
        return ((self.world_region,) if self.world_region is not None else ()) + self.regions

    def region_for(self, region_uid: EntityUid) -> TerrainRegionExtent | None:
        return next((r for r in self.all_regions() if r.region_uid == region_uid), None)


class TerrainRegionPlan(TerrainRegionModel, frozen=True):
    snapshot: TerrainRegionsSnapshot
    coverages: tuple[RegionCoverage, ...]

    @model_validator(mode="after")
    def matching_extent_and_coverage(self) -> Self:
        extents = {r.region_uid: r.generation_area_fine2 for r in self.snapshot.all_regions()}
        if len({c.region_uid for c in self.coverages}) != len(self.coverages):
            raise ValueError("duplicate coverage UID in region plan")
        measured = {c.region_uid: sum(s.x1 - s.x0 for s in c.spans) for c in self.coverages}
        if measured != extents:
            raise ValueError("region extents must match exact coverage areas")
        return self
