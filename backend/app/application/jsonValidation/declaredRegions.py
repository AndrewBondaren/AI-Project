"""Collection checks shared by import, world patches and region operations."""

from pydantic import BaseModel

from app.application.jsonValidation.resolve import ResolveContext, report_issues, resolve_model
from app.application.jsonValidation.types import ImportIssue
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.application.jsonValidation.worldSlices import slice_column_key
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.terrainMasks.worldTerrainMasks import DECLARED_REGIONS
from app.dataModel.terrainMasks.regions.specs import REGION_NAME
from app.db.models.world import World


def _field_issue(ctx: ResolveContext, root: type[BaseModel] | None, loc: tuple[str, ...],
                 message: str, code: JsonValidationCode) -> ImportIssue:
    """F01 when ``loc`` is a declared field of ``root`` at ``ctx.location``; otherwise F09."""
    path = CheckedPath.from_pydantic_loc(root, loc) if root is not None else None
    if path is None:
        return WireShapeIssue(code=code, location=ctx.location.child(*loc), message=message)
    return JsonFieldError(code=code, path=path, location=ctx.location, wire_path=loc,
                          schema_id=ctx.schema_id, message=message)


def validate_declared_regions(world: World, ctx: ResolveContext) -> None:
    masks_ctx = ctx.child(slice_column_key(WorldTerrainMasks))
    masks = resolve_model(WorldTerrainMasks, world.terrain_masks, ctx=masks_ctx)
    regions_ctx = masks_ctx.child(bind_field(DECLARED_REGIONS).field)
    seen: set[str] = set()
    for index, spec in enumerate(masks.declared_regions):
        # Identity diagnostics share the request report/mode: the producer decides
        # severity by validate_only, whereas collisions always reject the operation.
        local = regions_ctx.child(index)
        identity = declared_region_identity(world.world_uid, spec, ctx=local)
        if identity.region_uid in seen:
            report_issues(ctx, [_field_issue(local, type(spec), (bind_field(REGION_NAME).field,),
                "duplicate declared region identity", JsonValidationCode.REGION_UID_CONFLICT)])
        seen.add(identity.region_uid)
