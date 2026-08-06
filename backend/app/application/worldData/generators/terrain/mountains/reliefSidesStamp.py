"""Resolve MountainSpec.sides from relief template (R33) when declare empty."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.mountainSideMaterialize import (
    resolve_sides_with_declare,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RESOLVE_FALLBACK,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_info, relief_warning
from app.application.worldData.generators.terrain.relief.templatePick import pick_template
from app.application.jsonValidation.worldRow import relief_pick_policy, relief_template_registry
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.specs import ReliefSideSpec
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSpec,
    form_side_count,
)
from app.db.models.world import World


def stamp_mountain_sides_from_relief(
    spec: MountainSpec,
    *,
    world: World,
    world_seed: str,
    templates_by_uid: dict[str, ReliefTemplate],
) -> MountainSpec:
    """Empty sides → pick mountain template + materialize; declare wins.

    R21 (RELIEF-T-2): missing candidates / missing body → all-SLOPE via
    ``fallback_kind``. Mode D (seeded 50/50) only when a live template has
    empty ``side_recipe``.
    """
    if spec.sides:
        relief_info(
            "mountain_sides",
            recipe_mode="declare",
            override="declare",
            N=len(spec.sides),
            kinds=",".join(s.kind.value for s in spec.sides),
        )
        return spec
    n = form_side_count(spec.form)
    registry = relief_template_registry(world)
    world_policy = relief_pick_policy(world)
    object_policy = getattr(spec, "relief_pick_policy", None)
    mountain_id = (
        spec.location_uid
        or f"{spec.origin_x_m},{spec.origin_y_m},{spec.radius_m}"
    )
    pick = pick_template(
        context=ReliefContext.MOUNTAIN,
        registry=registry,
        world_policy=world_policy,
        world_seed=world_seed,
        site_id=mountain_id,
        object_policy=object_policy if isinstance(object_policy, ObjectReliefPickPolicy) else None,
    )

    template: ReliefTemplate | None = None
    if pick.template_uid and pick.template_uid in templates_by_uid:
        template = templates_by_uid[pick.template_uid]
    elif pick.template_uid:
        relief_warning(
            EVENT_RESOLVE_FALLBACK,
            context=ReliefContext.MOUNTAIN.value,
            why=f"missing_body={pick.template_uid}",
            chosen_fallback="SLOPE",
            site_id=mountain_id,
        )

    if template is None:
        # R21: no template / no body — not Mode D
        kind = pick.fallback_kind or ReliefSideKind.SLOPE
        sides = [ReliefSideSpec(kind=kind) for _ in range(n)]
        relief_info(
            "mountain_sides",
            template_uid=pick.template_uid,
            recipe_mode=EVENT_RESOLVE_FALLBACK,
            N=n,
            kinds=",".join(s.kind.value for s in sides),
            reason=pick.reason,
        )
        return spec.model_copy(update={"sides": sides})

    sides = resolve_sides_with_declare(
        n=n,
        recipe=template.side_recipe,
        world_seed=world_seed,
        template_uid=pick.template_uid or template.system_name,
        mountain_id=mountain_id,
        declare_sides=[],
    )
    return spec.model_copy(update={"sides": sides})


def stamp_entries_from_relief(
    entries: list[MountainSpec | MountainRangeSpec],
    *,
    world: World,
    world_seed: str,
    templates_by_uid: dict[str, ReliefTemplate],
) -> list[MountainSpec | MountainRangeSpec]:
    out: list[MountainSpec | MountainRangeSpec] = []
    for entry in entries:
        if isinstance(entry, MountainSpec):
            out.append(
                stamp_mountain_sides_from_relief(
                    entry,
                    world=world,
                    world_seed=world_seed,
                    templates_by_uid=templates_by_uid,
                )
            )
        elif isinstance(entry, MountainRangeSpec):
            peaks = [
                stamp_mountain_sides_from_relief(
                    p,
                    world=world,
                    world_seed=world_seed,
                    templates_by_uid=templates_by_uid,
                )
                for p in entry.peaks
            ]
            out.append(entry.model_copy(update={"peaks": peaks}))
        else:
            out.append(entry)
    return out
