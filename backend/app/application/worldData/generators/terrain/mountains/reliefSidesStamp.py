"""Resolve MountainSpec.sides from relief template (R33) when declare empty."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.generators.terrain.relief.mountain.mountainSideMaterialize import (
    resolve_sides_with_declare,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_info
from app.application.worldData.generators.terrain.relief.pick.templatePick import (
    pick_template,
    resolve_picked_template,
)
from app.application.jsonValidation.worldRow import relief_pick_policy
from app.application.jsonValidation.resolve import ResolveContext
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSpec,
    form_side_count,
)
from app.db.models.world import World


def _mountain_pick_site_id(spec: MountainSpec) -> str:
    """site_id for pick determinism — declared location uid, else geo tuple."""
    return (
        spec.location_uid
        or f"{spec.origin_x_m},{spec.origin_y_m},{spec.radius_m}"
    )


def _log_declared_sides(spec: MountainSpec) -> None:
    relief_info("mountain_sides", recipe_mode="declare", override="declare",
                N=len(spec.sides), kinds=",".join(side.kind.value for side in spec.sides))


def stamp_mountain_sides_from_relief(
    spec: MountainSpec,
    *,
    world: World,
    world_seed: str,
    templates_by_uid: Mapping[str, ReliefTemplate],
) -> MountainSpec:
    """Empty sides → pick mountain template + materialize; declare wins.

    E6-R21: missing candidates / missing body → shared unresolved.
    Mode D (seeded 50/50) only when a live template has
    empty ``side_recipe``.
    """
    if spec.sides:
        _log_declared_sides(spec)
        return spec
    return stamp_prepared_mountain_sides(spec, world_policy=relief_pick_policy(world).mountain,
        world_seed=world_seed, templates_by_uid=templates_by_uid)


def stamp_prepared_mountain_sides(
    spec: MountainSpec, *, world_policy: ReliefContextPickPolicy, world_seed: str,
    templates_by_uid: Mapping[str, ReliefTemplate | MountainTemplateInput],
    resolve_ctx: ResolveContext | None = None,
) -> MountainSpec:
    """Same declare/pick/recipe kernel using resolved policy and template projections."""
    if spec.sides:
        _log_declared_sides(spec)
        return spec
    n = form_side_count(spec.form)
    mountain_id = _mountain_pick_site_id(spec)
    pick = pick_template(
        context=ReliefContext.MOUNTAIN,
        templates=templates_by_uid,
        world_policy=world_policy,
        world_seed=world_seed,
        site_id=mountain_id,
        object_policy=spec.relief_pick_policy,
        resolve_ctx=resolve_ctx,
    )

    template = resolve_picked_template(pick, templates_by_uid, resolve_ctx=resolve_ctx)

    sides = resolve_sides_with_declare(
        n=n,
        recipe=template.side_recipe,
        world_seed=world_seed,
        template_uid=pick.template_uid,
        mountain_id=mountain_id,
        declare_sides=[],
    )
    return spec.model_copy(update={"sides": tuple(sides)})


def stamp_prepared_entry(
    entry: MountainSpec | MountainRangeSpec, *, world_policy: ReliefContextPickPolicy,
    world_seed: str, templates_by_uid: Mapping[str, MountainTemplateInput], resolve_ctx: ResolveContext,
) -> MountainSpec | MountainRangeSpec:
    if isinstance(entry, MountainSpec):
        return stamp_prepared_mountain_sides(entry, world_policy=world_policy, world_seed=world_seed,
            templates_by_uid=templates_by_uid, resolve_ctx=resolve_ctx)
    peaks = tuple(stamp_prepared_mountain_sides(peak, world_policy=world_policy, world_seed=world_seed,
        templates_by_uid=templates_by_uid, resolve_ctx=resolve_ctx) for peak in entry.peaks)
    return entry.model_copy(update={"peaks": peaks})


def stamp_entries_from_relief(
    entries: list[MountainSpec | MountainRangeSpec],
    *,
    world: World,
    world_seed: str,
    templates_by_uid: Mapping[str, ReliefTemplate],
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
            out.append(entry.model_copy(update={"peaks": tuple(peaks)}))
        else:
            out.append(entry)
    return out
