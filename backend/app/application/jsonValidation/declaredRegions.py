"""Collection checks shared by import, world patches and region operations."""

from app.application.jsonValidation.resolve import ResolveContext, report_issues, resolve_model
from app.application.jsonValidation.types import FieldPathError
from app.application.jsonValidation.worldSlices import slice_column_key
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.db.models.world import World


def validate_declared_regions(world: World, ctx: ResolveContext) -> None:
    masks_ctx = ctx.child(slice_column_key(WorldTerrainMasks))
    masks = resolve_model(WorldTerrainMasks, world.terrain_masks, ctx=masks_ctx)
    regions_ctx = masks_ctx.child("declared_regions")
    seen: set[str] = set()
    for index, spec in enumerate(masks.declared_regions):
        # Identity diagnostics use a local report: anonymous runtime regions are
        # usable, whereas collisions always reject the complete operation.
        local = ResolveContext(path_prefix=regions_ctx.path_prefix + (index,), validate_only=ctx.validate_only)
        identity = declared_region_identity(world.world_uid, spec, ctx=local)
        if identity.region_uid in seen:
            report_issues(ctx, [FieldPathError(local.path_prefix + ("name",),
                "duplicate declared region identity", code="REGION_UID_CONFLICT")])
        seen.add(identity.region_uid)
