import logging
from random import Random

from app.application.jsonValidation import economic_tiers, materials
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.ids import UidKind, entity_rng
from app.application.worldData.generators.utils.tierRegistry import median_system_tier, tiers_sorted
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.db.models.world import World

from app.dataModel.materials import (
    DEFAULT_DOMINANT_MATERIAL,
    DEFAULT_FLOOR_MATERIAL,
    DEFAULT_WALL_MATERIAL,
)

logger = logging.getLogger(__name__)


def _construction_candidates(
    registry: list[MaterialRegistryEntry],
    use_type: str,
    tier: str,
) -> list[str]:
    return [
        entry.system_material
        for entry in registry
        if "construction" in entry.tags
        and use_type in entry.use_type
        and entry.economic_tier == tier
    ]


def resolve_material(
    world: World,
    use_type: str,
    effective_tier: str | None,
    rng: Random,
    default: str,
    context: str = "",
) -> str:
    """
    Выбирает материал из material_registry по use_type и economic_tier.
    Fallback: ближайший тир вниз → любой подходящий → default.
    """
    registry = materials(world).root
    tiers = tiers_sorted(economic_tiers(world).root)
    ctx = ResolveContext(path_prefix=("materials", context or use_type))
    if effective_tier is not None and not any(e.system_tier == effective_tier for e in tiers):
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix + ("economic_tier",),
            f"unknown reference: {effective_tier!r}", code="REF_W_UNKNOWN")])
    # Canonical completion is a catalog contract; validate authored row refs,
    # not builtin rows whose tier vocabulary may differ from a custom world.
    by_key = {entry.system_material: entry for entry in registry}
    for index, raw in enumerate(world.material_registry or []):
        # The accessor above validated canonical overlays. Read effective rows
        # for authored keys rather than revalidating partial overlay rows.
        entry = by_key[raw["system_material"]]
        if entry.economic_tier is not None and not any(t.system_tier == entry.economic_tier for t in tiers):
            reject_unresolved(ctx, [FieldPathError(("material_registry", index, "economic_tier"),
                f"unknown reference: {entry.economic_tier!r}", code="REF_W_UNKNOWN")])
    tier = effective_tier if effective_tier is not None else median_system_tier(tiers) or ""

    found = _construction_candidates(registry, use_type, tier)

    if not found:
        current_val = next(
            (entry.base_value for entry in tiers if entry.system_tier == tier),
            0,
        )
        for tier_entry in reversed([entry for entry in tiers if entry.base_value < current_val]):
            found = _construction_candidates(registry, use_type, tier_entry.system_tier)
            if found:
                break

    if not found:
        found = [
            entry.system_material
            for entry in registry
            if "construction" in entry.tags
            and use_type in entry.use_type
        ]

    if not found:
        # A declared default for ordinary absence is legal only if it names
        # a material in this world's valid vocabulary. Never invent a key.
        if any(entry.system_material == default for entry in registry):
            return default
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, f"no {use_type!r} material candidates or declared default {default!r}",
                                               code="DOMAIN_NO_CANDIDATE")])


    return rng.choice(found)


def fold_dominant_material(
    world:    World,
    objects,
    resolved: dict,
) -> str:
    """Cascade fold for ``dominant_material`` (tz_cascade_context §3,
    cascade-migration M10): tier → material_registry pick between the
    authored chain and the canonical default. Per-param stream over
    ``UidKind.CASCADE``, never shared with tier materialize (§4)."""
    if world is None:
        raise ValueError("dominant_material: fold requires world")
    scope_uid = next(
        (obj.location_uid for obj in objects
         if getattr(obj, "location_uid", None)),
        "",
    )
    fold_rng = entity_rng(
        world.world_uid, UidKind.CASCADE,
        scope=scope_uid, param="dominant_material",
    )
    return resolve_material(
        world, "wall", resolved.get("economic_tier"), fold_rng,
        DEFAULT_DOMINANT_MATERIAL,
    )


def resolve_room_materials(
    world: World,
    effective_tier: str | None,
    rng: Random,
    room_id: str = "",
) -> tuple[str, str]:
    """Возвращает (wall_material, floor_material) для комнаты.

    ``effective_tier`` — уже resolved room-scope значение каскада;
    резолва здесь нет (tz_cascade_context §4, cascade-migration M4).
    """
    wall  = resolve_material(world, "wall",  effective_tier, rng, DEFAULT_WALL_MATERIAL,  context=room_id)
    floor = resolve_material(world, "floor", effective_tier, rng, DEFAULT_FLOOR_MATERIAL, context=room_id)
    return wall, floor
