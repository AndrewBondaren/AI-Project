"""Complete relief inputs; foreign domain results arrive through dependencies."""

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from typing import Annotated, Self

from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.terrainMasks.mountain.specs import MountainDeclareEntry
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy, RavinesCategoryPolicy
from app.dataModel.topology.worldTopology import WorldTopology


class TerrainMergeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: TerrainKey
    merge_rank: StrictInt


def require_terrain_merge(entries: tuple[TerrainMergeEntry, ...]) -> None:
    keys = tuple(entry.key for entry in entries)
    if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
        raise ValueError("terrain merge keys must be unique and sorted")


from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput, require_mountain_templates


class MountainAnchorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    location_uid: EntityUid
    position: FineXY


class ReliefPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    seed: StrictInt
    masks_enabled: StrictBool
    mountains: MountainsCategoryPolicy
    ravines: RavinesCategoryPolicy
    declared_mountains: tuple[MountainDeclareEntry, ...]
    anchors: tuple[MountainAnchorInput, ...]
    grid: SurfaceGridSettings
    z_min: FineZ
    z_max: FineZ
    mountain_templates: tuple[MountainTemplateInput, ...]
    mountain_pick: ReliefContextPickPolicy
    terrain_merge: tuple[TerrainMergeEntry, ...]

    @model_validator(mode="after")
    def valid_inputs(self) -> Self:
        if self.z_min > self.z_max:
            raise ValueError("z_min exceeds z_max")
        require_mountain_templates(self.mountain_templates)
        require_terrain_merge(self.terrain_merge)
        return self


class RiverReliefInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    z_min: FineZ
    z_max: FineZ
    grid: SurfaceGridSettings
    topology: WorldTopology
    channel_depths: tuple[tuple[HydrologyConnectionType, Annotated[StrictInt, Field(gt=0)]], ...]

    @model_validator(mode="after")
    def complete_depths(self) -> Self:
        if self.z_min > self.z_max:
            raise ValueError("z_min exceeds z_max")
        kinds = tuple(kind for kind, _ in self.channel_depths)
        expected = {HydrologyConnectionType.RIVER, HydrologyConnectionType.MOUNTAIN_RIVER}
        if len(kinds) != len(expected) or set(kinds) != expected:
            raise ValueError("channel depths require exactly the river policy connection types")
        if kinds != tuple(sorted(kinds, key=lambda kind: kind.value)):
            raise ValueError("channel depths require canonical connection type order")
        return self
