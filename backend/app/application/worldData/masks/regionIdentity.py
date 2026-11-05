"""Declared Spec identity/revision with the shared author/runtime diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues, resolve_model
from app.dataModel.terrainMasks.regions.identityIssue import RegionIdentityCode, RegionIdentityIssue
from app.dataModel.spatial.regionShape import AnchorRadiusShape
from app.dataModel.terrainMasks.regions import RegionSpecBase
from app.dataModel.terrainMasks.regions.specs import REGION_NAME
from app.dataModel.fields.checkedPath import CheckedPath
from app.ids.deterministicIds import state_fingerprint
from app.ids.regionIdentity import region_uid


@dataclass(frozen=True)
class RegionIdentity:
    region_uid: str
    spec_fingerprint: str


def declared_region_identity(
    world_uid: str,
    spec: RegionSpecBase,
    *,
    ctx: ResolveContext | None = None,
) -> RegionIdentity:
    """Validate before deriving identity; anonymous regions are an author error but stay usable at runtime."""
    active = ctx if ctx is not None else ResolveContext()
    # Revalidate even typed input: model_copy/model_construct may bypass validators.
    spec = resolve_model(type(spec), spec.model_dump(mode="json"), ctx=active)
    if spec.name is not None:
        uid = region_uid(world_uid, name=spec.name)
    else:
        if isinstance(spec.shape, AnchorRadiusShape):
            uid = region_uid(world_uid, anchor_uid=spec.shape.anchor_uid)
        else:
            x_min, y_min, _, _ = spec.shape.bbox()
            uid = region_uid(world_uid, bbox_min=(x_min, y_min), shape_kind=spec.shape.kind)
        issue = RegionIdentityIssue(
            path=CheckedPath.root(RegionSpecBase).field(REGION_NAME).freeze(),
            location=active.location,
            message=f"landcover | degraded_identity | region_uid={uid}; declared region has no name",
            schema_id=active.schema_id,
            code=RegionIdentityCode.REGION_DEGRADED_IDENTITY,
        )
        if active.validate_only or active.collect_only:
            report_issues(active, [issue])
        else:
            log_issues([issue])
    return RegionIdentity(uid, state_fingerprint(spec.model_dump(mode="json")))
