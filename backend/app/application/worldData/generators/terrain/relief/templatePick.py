"""Pick relief template by policy — side > object > world (R19/R21/R31)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RESOLVE_FALLBACK,
)
from app.application.worldData.generators.terrain.relief.reliefLog import (
    relief_info,
    relief_warning,
)
from app.application.worldData.generators.terrain.relief.seededHash import seeded_index
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
) -> ReliefTemplate | None:
    """Load template body for a pick (RELIEF-T-36).

    Returns ``None`` when uid is missing or body is not in ``templates_by_uid``.
    Caller owns R21 policy (ribbon skip vs mountain fallback).
    """
    uid = pick.template_uid
    if not uid:
        return None
    return templates_by_uid.get(uid)


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
) -> PickResult:
    ctx = context.value if isinstance(context, ReliefContext) else context
    effective, level = merge_pick_policy(
        context=ctx,
        world=world_policy,
        object_policy=object_policy,
        side_policy=side_policy,
    )
    candidates = registry.entries_for_context(ctx)
    if not candidates:
        relief_warning(
            EVENT_RESOLVE_FALLBACK,
            context=ctx,
            mode=effective.mode.value,
            why="empty_candidates",
            chosen_fallback=ReliefSideKind.SLOPE.value,
            policy_level=level,
        )
        return PickResult(
            template_uid=None,
            policy_level="fallback",
            mode=effective.mode,
            reason="empty_candidates",
            fallback_kind=ReliefSideKind.SLOPE,
        )

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
        relief_warning(
            EVENT_RESOLVE_FALLBACK,
            context=ctx,
            mode="fixed",
            why=f"missing_uid={uid}",
            chosen_fallback=candidates[0].system_template_uid,
            policy_level=level,
        )
        return PickResult(
            template_uid=candidates[0].system_template_uid,
            policy_level="fallback",
            mode=effective.mode,
            reason=f"fixed_uid_missing:{uid}",
        )

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
        f"{world_seed}|relief_pick|{ctx}|{site_id}",
        len(candidates),
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
