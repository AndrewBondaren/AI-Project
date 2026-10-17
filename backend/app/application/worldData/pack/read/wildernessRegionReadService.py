"""Debug selector reads manifest snapshots; outlines derive geometry from world data."""
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import require_surface_terrain_context
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.render.regions.regionOutline import render_region_outline
from app.dataModel.worldPack.meta.wildernessRegionDebug import WildernessRegionSnapshot, WildernessRegionOutline
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation


class RegionOutlineStaleError(ValueError):
    pass


class WildernessRegionReadService:
    def __init__(self, context: PackReadContext) -> None:
        self._context = context

    def get_snapshot(self, world: World, region_uid: str) -> WildernessRegionSnapshot | None:
        if not self._context.has_pack_for(world):
            return None
        entry = self._context.reader_for(world).manifest.wilderness_region_entry(region_uid)
        return WildernessRegionSnapshot(entry=entry) if entry is not None else None

    def outline(self, world: World, locations: list[NamedLocation], region_uid: str) -> WildernessRegionOutline | None:
        if self.get_snapshot(world, region_uid) is None:
            return None
        manifest = self._context.reader_for(world).manifest
        surface = require_surface_terrain_context(world, locations)
        ctx = LightGridBakeContext(world, locations, build_locations_index(locations,world), [],
            LightGridScale.from_tile(manifest.fine_cells_per_map_cell,manifest.world_map_cells_per_tile),
            surface_planning=surface)
        outline = render_region_outline(ctx,region_uid)
        if outline is None:
            raise RegionOutlineStaleError("region snapshot has no matching region in current world data; re-bake the index")
        return WildernessRegionOutline(region_uid=region_uid,outline=outline)
