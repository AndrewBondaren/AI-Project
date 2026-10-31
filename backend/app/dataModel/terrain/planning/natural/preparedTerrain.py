"""Ready natural geometry; window requests never repeat its feature selection."""
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.terrain.hills.acceptedHill import HillLayout
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan
from app.dataModel.terrain.relief.planning.reliefPlan import LightReliefPlan, MountainLayout
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy

type NaturalTerrainInputs = tuple[TerrainBaseInput, ReliefPlanInput, SurfaceSupportInput]


class NaturalTerrainTile(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    gx: GridX
    gy: GridY
    protected_spans: tuple[CoverageSpan, ...]
    hills: HillLayout | None

    @model_validator(mode="after")
    def ordered_protection(self) -> Self:
        previous: CoverageSpan | None = None
        for span in self.protected_spans:
            if previous is not None and (span.y < previous.y or span.y == previous.y and span.x0 <= previous.x1):
                raise ValueError("protected intervals must be canonical")
            previous = span
        return self


class PreparedNaturalTerrain(BaseModel):
    model_config = NaturalTerrainTile.model_config

    base: TerrainBaseInput
    topology: WorldTopology
    refine_policy: ParentLightRefinePolicy
    mountain_layout: MountainLayout
    light: LightReliefPlan
    tiles: tuple[NaturalTerrainTile, ...]

    @model_validator(mode="after")
    def coherent_extent(self) -> Self:
        keys = tuple((t.gy, t.gx) for t in self.tiles)
        box, span = self.base.bbox, self.base.grid.fine_span
        expected = tuple((y, x) for y in range(box.y_min, box.y_max+1) for x in range(box.x_min, box.x_max+1))
        if keys != expected:
            raise ValueError("natural preparation must cover the captured canonical tile extent")
        b = self.topology.bounds
        if (b.x_min, b.x_max, b.y_min, b.y_max) != (
                box.x_min*span, (box.x_max+1)*span-1, box.y_min*span, (box.y_max+1)*span-1):
            raise ValueError("prepared natural topology must be in matching fine coordinates")
        light_keys = {(c.gy, c.gx) for c, _ in self.light.base_surface_z}
        if light_keys != set(keys):
            raise ValueError("prepared natural light must match tile coverage")
        side = self.base.grid.light_side
        if len(self.light.base_surface_z) != len(keys)*side*side or any(
                not (0 <= c.tx < side and 0 <= c.ty < side) for c, _ in self.light.base_surface_z):
            raise ValueError("prepared natural light must be complete within each tile")
        for tile in self.tiles:
            if any(not (tile.gx*span <= s.x0 < s.x1 <= (tile.gx+1)*span
                        and tile.gy*span <= s.y < (tile.gy+1)*span) for s in tile.protected_spans):
                raise ValueError("protected intervals outside their prepared tile")
        return self
