"""Pick relief template by policy — side > object > world (R19/R21/R31)."""

from __future__ import annotations

from collections.abc import Mapping
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.log.log import (
    relief_info,
)
from app.application.worldData.generators.terrain.relief.geom.seededHash import seeded_index
from app.ids import UidKind
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefPickMode, ReliefSideKind
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ObjectReliefPickPolicy,
    ReliefContextPickPolicy,
    WorldReliefPickPolicy,
)
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import (
    WorldReliefTemplateRegistry,
)

@dataclass(frozen=True, slots=True)
class PickResult:
    template_uid: str | None
    policy_level: str  # side | object | world | fallback
    mode: ReliefPickMode | None
    reason: str
    fallback_kind: ReliefSideKind | None = None


def resolve_picked_template(
    pick: PickResult,
    templates_by_uid: Mapping[str, ReliefTemplate],
    *, resolve_ctx: ResolveContext | None = None,
) -> ReliefTemplate:
    """Resolve the selected body; missing required bodies are unresolved."""
    ctx = resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("relief_templates",))
    uid = pick.template_uid
    template = templates_by_uid.get(uid) if uid else None
    if template is None:
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix + (uid or "selected",),
            "selected template body unavailable", code="REF_W_UNAVAILABLE")])
    return template


def merge_pick_policy(
    *,
    context: ReliefContext | str,
    world: WorldReliefPickPolicy,
    object_policy: ObjectReliefPickPolicy | None = None,
    side_policy: ObjectReliefPickPolicy | None = None,
) -> tuple[ReliefContextPickPolicy, str]:
    """R31: side > object > world.

    v1: ``side_policy`` reserved (RELIEF-T-5 / TZ R31 deferred); consumers pass None.
    """
    ctx = context.value if isinstance(context, ReliefContext) else context
    if side_policy is not None:
        side = side_policy.for_context(ctx)
        if side is not None:
            return side, "side"
    if object_policy is not None:
        obj = object_policy.for_context(ctx)
        if obj is not None:
            return obj, "object"
    return world.for_context(ctx), "world"


def pick_template(
    *,
    context: ReliefContext | str,
    registry: WorldReliefTemplateRegistry,
    world_policy: WorldReliefPickPolicy,
    world_seed: str,
    site_id: str,
    occurrence_seq: int = 0,
    object_policy: ObjectReliefPickPolicy | None = None,
    side_policy: ObjectReliefPickPolicy | None = None,
    resolve_ctx: ResolveContext | None = None,
) -> PickResult:
    ctx = context.value if isinstance(context, ReliefContext) else context
    effective, level = merge_pick_policy(
        context=ctx,
        world=world_policy,
        object_policy=object_policy,
        side_policy=side_policy,
    )
    active = resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("relief_pick", ctx, site_id))
    candidates = registry.entries_for_context(ctx)
    if not candidates:
        reject_unresolved(active, [FieldPathError(active.path_prefix,
            "no relief template candidates", code="DOMAIN_NO_CANDIDATE")])

    if effective.mode == ReliefPickMode.FIXED:
        uid = effective.default_template_uid
        if uid and any(e.system_template_uid == uid for e in candidates):
            result = PickResult(
                template_uid=uid,
                policy_level=level,
                mode=effective.mode,
                reason="fixed",
            )
            relief_info(
                "pick",
                context=ctx,
                template_uid=uid,
                pick_mode="fixed",
                policy_level=level,
                site_id=site_id,
            )
            return result
        reject_unresolved(active, [FieldPathError(active.path_prefix + ("default_template_uid",),
            f"fixed template unavailable in context: {uid!r}", code="REF_W_UNKNOWN")])

    if effective.mode == ReliefPickMode.ROUND_ROBIN:
        idx = occurrence_seq % len(candidates)
        uid = candidates[idx].system_template_uid
        relief_info(
            "pick",
            context=ctx,
            template_uid=uid,
            pick_mode="round_robin",
            policy_level=level,
            site_id=site_id,
            seq=occurrence_seq,
        )
        return PickResult(
            template_uid=uid,
            policy_level=level,
            mode=effective.mode,
            reason=f"round_robin seq={occurrence_seq}",
        )

    # random
    idx = seeded_index(
        world_seed, UidKind.RELIEF_PICK, len(candidates),
        context=ctx, site=site_id,
    )
    uid = candidates[idx].system_template_uid
    relief_info(
        "pick",
        context=ctx,
        template_uid=uid,
        pick_mode="random",
        policy_level=level,
        site_id=site_id,
    )
    return PickResult(
        template_uid=uid,
        policy_level=level,
        mode=effective.mode,
        reason="random",
    )
