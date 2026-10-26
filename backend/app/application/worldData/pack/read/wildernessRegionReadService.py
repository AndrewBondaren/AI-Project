"""Debug selector reads manifest snapshots; outlines derive geometry from world data."""
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.worldData.generators.terrain.landcover.types import LandcoverCollectContext
from app.application.worldData.regions.inputs.landcoverInputs import prepare_landcover_inputs
from app.application.worldData.regions.regionStateSnapshot import load_region_state_snapshot
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.render.regions.regionOutline import render_region_outline
from app.dataModel.worldPack.meta.wildernessRegionDebug import WildernessRegionSnapshot, WildernessRegionOutline
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation


class RegionOutlineStaleError(ValueError):
    pass


class WildernessRegionReadService:
    def __init__(self, context: PackReadContext, *, planning: SurfacePlanningAssembler | None = None,
                 capture: SurfacePlanningCapture | None = None,
                 region_state_repo: IRegionStateRepository | None = None) -> None:
        self._planning, self._capture = planning, capture
        self._context = context
        self._region_state_repo = region_state_repo

    def get_snapshot(self, world: World, region_uid: str) -> WildernessRegionSnapshot | None:
        if not self._context.has_pack_for(world):
            return None
        entry = self._context.reader_for(world).manifest.wilderness_region_entry(region_uid)
        return WildernessRegionSnapshot(entry=entry) if entry is not None else None

    async def outline(self, world: World, locations: list[NamedLocation], region_uid: str, *, wait: PlanWaitControl) -> WildernessRegionOutline | None:
        # TODO(snapshot): integrate snapshot existence lookup via the shared CRUD;
        # see .cursor/plans/world-state-crud-transition.md, section 7 (PC-11 and future snapshots).
        if self.get_snapshot(world, region_uid) is None:
            return None
        manifest = self._context.reader_for(world).manifest
        if self._planning is None or self._capture is None:
            raise ValueError("surface planning dependencies required")
        if self._region_state_repo is None:
            raise ValueError("region state repository required for outline")
        _, working = SurfacePlanningEntry(self._planning, self._capture).require_plan_inputs(
            world, locations, wait=wait)
        snapshot = await load_region_state_snapshot(self._region_state_repo, world.world_uid)
        inputs = prepare_landcover_inputs(working, snapshot)
        ctx = LandcoverCollectContext(world, tuple(locations),
            LightGridScale.from_tile(manifest.fine_cells_per_map_cell, manifest.world_map_cells_per_tile), ())
        outline = render_region_outline(ctx, inputs, region_uid)
        if outline is None:
            raise RegionOutlineStaleError("region snapshot has no matching region in current world data; re-bake the index")
        return WildernessRegionOutline(region_uid=region_uid,outline=outline)
