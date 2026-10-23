"""Pre-river relief and post-river bed contracts — PC-0 §6.31 B–D."""

from collections.abc import Callable
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ, LightCellRef, SurfaceGridCoord
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.terrainMasks.mountain.specs import MountainDeclareEntry, MountainSpec, form_side_count


class MountainTemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    template_uid: EntityUid
    context: ReliefContext
    side_recipe: MountainSideRecipe | None

    @model_validator(mode="after")
    def mountain_context(self) -> Self:
        if self.context != ReliefContext.MOUNTAIN:
            raise ValueError("mountain template requires mountain context")
        return self


def require_mountain_templates(templates: tuple[MountainTemplateInput, ...]) -> None:
    uids = tuple(template.template_uid for template in templates)
    if len(set(uids)) != len(uids) or uids != tuple(sorted(uids)):
        raise ValueError("mountain template UIDs must be unique and sorted")


# The input owner defines TerrainMergeEntry before importing MountainTemplateInput.
# This keeps both planned public entry points usable in either import order.
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import TerrainMergeEntry, require_terrain_merge


class MountainLayout(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[MountainDeclareEntry, ...]
    templates: tuple[MountainTemplateInput, ...]
    world_pick: ReliefContextPickPolicy
    terrain_key: TerrainKey

    @model_validator(mode="after")
    def stamped_entries(self) -> Self:
        require_mountain_templates(self.templates)
        identities = tuple(entry.identity_key() for entry in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate mountain identity")
        for entry in self.entries:
            peaks = (entry,) if isinstance(entry, MountainSpec) else entry.peaks
            if any(len(peak.sides) != form_side_count(peak.form) for peak in peaks):
                raise ValueError("mountain layout requires fully resolved peak sides")
        return self


def require_coordinate_map[K](rows: tuple[tuple[K, FineZ], ...], order: Callable[[K], tuple[int, ...]]) -> None:
    coords = tuple(coord for coord, _ in rows)
    if len(set(coords)) != len(coords):
        raise ValueError("duplicate relief coordinate")
    if coords != tuple(sorted(coords, key=order)):
        raise ValueError("relief coordinates require canonical order")


def light_order(cell: LightCellRef) -> tuple[int, ...]:
    if cell.tx < 0 or cell.ty < 0:
        raise ValueError("light offsets must be nonnegative")
    return cell.gy, cell.gx, cell.ty, cell.tx


def coarse_order(cell: SurfaceGridCoord) -> tuple[int, ...]:
    return cell.gy, cell.gx


def fine_order(cell: FineXY) -> tuple[int, ...]:
    return cell[1], cell[0]


class LightMountainCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    cell: LightCellRef
    surface_z: FineZ
    facing: Facing | None


class LightRavineCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    cell: LightCellRef
    surface_z: FineZ


class LightReliefPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    base_surface_z: tuple[tuple[LightCellRef, FineZ], ...]
    mountain_cells: tuple[LightMountainCell, ...]
    ravine_cells: tuple[LightRavineCell, ...]
    ravine_terrain: TerrainKey
    terrain_merge: tuple[TerrainMergeEntry, ...]

    @model_validator(mode="after")
    def consistent_light_maps(self) -> Self:
        require_coordinate_map(self.base_surface_z, light_order)
        require_terrain_merge(self.terrain_merge)
        base = {cell for cell, _ in self.base_surface_z}
        for effects in (self.mountain_cells, self.ravine_cells):
            rows = tuple((effect.cell, effect.surface_z) for effect in effects)
            require_coordinate_map(rows, light_order)
            if any(cell not in base for cell, _ in rows):
                raise ValueError("light relief effect outside base surface")
        return self


class ReliefPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]
    mountain_layout: MountainLayout
    light: LightReliefPlan

    @model_validator(mode="after")
    def consistent_surface(self) -> Self:
        require_coordinate_map(self.surface_z, coarse_order)
        coarse = {(cell.gx, cell.gy) for cell, _ in self.surface_z}
        light = {(cell.gx, cell.gy) for cell, _ in self.light.base_surface_z}
        if coarse != light:
            raise ValueError("coarse and light relief require the same macro extent")
        return self


S = TypeVar("S")


class RiverBedRecord(BaseModel, Generic[S]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    river_uid: EntityUid
    bed_z: tuple[tuple[S, FineZ], ...]

    @model_validator(mode="after")
    def unique_cells(self) -> Self:
        if len({cell for cell, _ in self.bed_z}) != len(self.bed_z):
            raise ValueError("duplicate river bed coordinate")
        return self


class RiverReliefPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]
    fine_surface_z: tuple[tuple[FineXY, FineZ], ...]
    coarse_beds: tuple[RiverBedRecord[SurfaceGridCoord], ...]
    fine_beds: tuple[RiverBedRecord[FineXY], ...]

    @model_validator(mode="after")
    def consistent_beds(self) -> Self:
        require_coordinate_map(self.surface_z, coarse_order)
        require_coordinate_map(self.fine_surface_z, fine_order)
        for beds in (self.coarse_beds, self.fine_beds):
            if len({bed.river_uid for bed in beds}) != len(beds):
                raise ValueError("duplicate river UID in coordinate space")
        coarse = {cell for cell, _ in self.surface_z}
        fine = {cell for cell, _ in self.fine_surface_z}
        for bed in self.coarse_beds:
            require_coordinate_map(bed.bed_z, coarse_order)
            if any(cell not in coarse for cell, _ in bed.bed_z):
                raise ValueError("coarse river bed outside surface")
        for bed in self.fine_beds:
            require_coordinate_map(bed.bed_z, fine_order)
            if any(cell not in fine for cell, _ in bed.bed_z):
                raise ValueError("fine river bed outside sampled surface")
        return self
