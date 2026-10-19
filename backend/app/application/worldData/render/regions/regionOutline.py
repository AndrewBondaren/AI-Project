"""Region debug outline from collect geometry, using the shared raster and ASCII kernel."""
from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import claim_owners
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.contributors.landcoverInputs import prepare_landcover_inputs
from app.application.worldData.pack.bake.lightGrid.coords import light_cell_center_fine
from app.application.worldData.render.fineTerrainAsciiKernel import draw_symbol_grid
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.dataModel.worldPack.wire.worldBounds import WorldBounds
from app.dataModel.worldPack.wire.worldTopology import WorldTopology
from app.ids import seed_root


def render_region_outline(ctx: LightGridBakeContext, region_uid: str) -> str | None:
    """Derive a L0 outline, independent of which bake tiles currently exist."""
    masks = terrain_masks(ctx.world)
    if masks.default_landcover is None or not masks.category_enabled(masks.default_landcover):
        return None
    plugin = LandcoverMaterializer(prepare_landcover_inputs(ctx))
    plugin.begin_pass()
    regions = plugin.collect(ctx, plugin.category_policy(masks))
    for region in regions:
        sub = next((s for s in region.sublocations if s.region_uid == region_uid), None)
        if region.region_uid != region_uid and sub is None:
            continue
        cells = plugin.materialize(region, ctx.scale).cells
        if sub is not None:
            if region.claim is None:
                raise ValueError("sublocation outline requires its source claim")
            raster = RegionRasterContext(region.region_uid, region.spec, ctx.scale, region.topology)
            owners = claim_owners(region.claim, seed_root(ctx.world), raster.fine_topology())
            cells = frozenset(c for c in cells if (
                (owner := owners.get(light_cell_center_fine(c.gx,c.gy,c.tx,c.ty,ctx.scale))) is not None
                and owner.coord == sub.seed_xy))
        side = ctx.scale.side
        points = {(c.gx*side+c.tx,c.gy*side+c.ty) for c in cells}
        b = region.topology.bounds
        topology = WorldTopology(mode=region.topology.mode, bounds=WorldBounds(
            x_min=b.x_min*side, y_min=b.y_min*side,
            x_max=(b.x_max+1)*side-1, y_max=(b.y_max+1)*side-1))
        symbols = {}
        for point in points:
            edge = False
            for facing in CARDINAL_FACINGS:
                neighbor = topology.neighbor(*point, facing)
                if neighbor is None or neighbor.coord not in points:
                    edge = True
                    break
            symbols[point] = "#" if edge else "."
        return draw_symbol_grid(symbols, title=f"region {region_uid} (derived L0 outline)",
            extra_headers=["# boundary; . interior; world data, not manifest geometry"],
            coord_prefix="light ", fine_span=ctx.scale.light_span, x_rulers=False)
    return None
