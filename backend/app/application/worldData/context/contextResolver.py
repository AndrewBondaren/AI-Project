"""Generic cascade resolver — tz_cascade_context §4.

``extend()`` is the single generic engine: it validates the link
sequence against the scope axis, accumulates the provided source POJOs,
and re-resolves every ``Cascade`` parameter — but only the nodes of
the **new** level are walked. Each chain node is resolved exactly
once, at the boundary of its own scope; the inherited resolved value
is both the materialize anchor and the fallback. That is what makes
materialization happen once: a band authored at area materializes at
the area boundary and is never re-rolled by deeper scopes.

One resolution per scope: the caller supplies the rng for the scope
(``Random(_make_seed(world_uid, scope_uid, param))``); a materialize
channel that needs it (no anchor) requires it — missing rng is a
caller bug, never a silent skip.
"""

from random import Random

from pydantic import BaseModel

from app.application.jsonValidation import economic_tiers
from app.application.worldData.context.cascadeLink import Link
from app.application.worldData.context.cascadeLog import (
    log_default_applied,
    log_scope_resolve,
)
from app.application.worldData.generators.utils.economicTierBands import (
    materialize_tier_input,
)
from app.application.worldData.generators.utils.materialResolver import (
    fold_dominant_material,
)
from app.dataModel.locations.context.cascadeParams import (
    CITY_SIZE,
    DOMINANT_MATERIAL,
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    SETTLEMENT_DENSITY,
    WALL_MATERIAL,
)
from app.dataModel.cascade.cascadeGraph import (
    check_link,
    ordered_chain,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    ChannelKind,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.settlement.enums.districtDensity import (
    DistrictDensity,
)
from app.dataModel.materials import (
    CONSTRUCTION_MATERIAL_DEFAULTS,
)
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)


def extend(
    ctx: LocationContext, *links: Link, rng: Random | None = None,
) -> LocationContext:
    """Add one scope level of links; return a new resolved context."""
    levels = {link.level for link in links}
    if len(levels) != 1:
        raise ValueError(
            "extend() takes links of exactly one scope level"
        )
    level = levels.pop()
    if type(level) is not type(ctx.level):
        raise ValueError(
            f"link axis {type(level).__name__} does not match "
            f"context axis {type(ctx.level).__name__}"
        )
    if level.rank <= ctx.level.rank:
        raise ValueError(
            f"level {level.value} is not strictly below "
            f"{ctx.level.value}"
        )
    if level.rank > ctx.level.rank + 1:
        raise ValueError(
            f"level {level.value} skips a level after "
            f"{ctx.level.value}"
        )
    objects = []
    for link in links:
        if link.obj is None:
            continue
        check_link(level, link.obj)
        objects.append(link.obj)

    stored = dict(ctx._links)
    stored[level] = tuple(objects)

    provenance = dict(ctx.provenance)
    update = {"level": level}
    params: dict[str, str] = {}

    def _resolve_field(name: str, param: Cascade) -> None:
        inherited_source = ctx.provenance.get(name)
        value, source = _resolve(
            param, level, objects, getattr(ctx, name),
            inherited_source, ctx._world, rng,
        )
        if source is None:
            if _is_default(inherited_source):
                # The same provisional default still stands — do not
                # re-warn at every empty scope.
                value, source = getattr(ctx, name), inherited_source
            else:
                if param.fold is not None:
                    value, source = _apply_fold(
                        param, level, objects, update, ctx._world,
                    )
                if source is None:
                    value = _resolve_default(param, ctx._world)
                    source = (next(iter(param.axis)),
                              f"default:{param.default.value}")
                    log_default_applied(
                        param=param.field,
                        level=level.value,
                        policy=param.default,
                        value=value,
                    )
        update[name] = value
        provenance[name] = source
        parent = (
            f"{inherited_source[0].value}.{inherited_source[1]}"
            if inherited_source is not None
            else "none"
        )
        child = (
            f"{source[0].value}.{source[1]}"
            if source != inherited_source
            else "none"
        )
        params[name] = f"{value} parent={parent} child={child}"

    cascade_fields = [
        (name, param)
        for name, info in LocationContext.model_fields.items()
        for param in (
            next(
                (m for m in info.metadata if isinstance(m, Cascade)),
                None,
            ),
        )
        if param is not None
    ]
    # Fold params resolve in a second pass — their resolver reads this
    # level's freshly resolved values (e.g. the dominant-material pick
    # uses the tier resolved at this same scope).
    for name, param in cascade_fields:
        if param.fold is None:
            _resolve_field(name, param)
    for name, param in cascade_fields:
        if param.fold is not None:
            _resolve_field(name, param)
    update["provenance"] = provenance
    new_ctx = ctx.model_copy(update=update)
    new_ctx._world = ctx._world
    new_ctx._links = stored
    log_scope_resolve(
        level=level.value,
        objects=[type(obj).__name__ for obj in objects],
        params=params,
    )
    return new_ctx


def _is_default(source) -> bool:
    return bool(source) and source[1].startswith("default:")


def _resolve(param, level, objects, inherited, inherited_source, world, rng):
    """Walk the new level's chain nodes; materialize once, anchored to
    the inherited value; fall through to inheritance."""
    # A provisional default is not an authored anchor — a deeper
    # materialize rolls instead of clamping to the median.
    anchor = None if _is_default(inherited_source) else inherited
    for owner, node, channel in ordered_chain(param):
        if node.level is not level:
            continue
        obj = _link_object(objects, owner)
        if obj is None:
            continue
        raw = getattr(obj, node.field)
        if raw is None:
            continue
        if channel.kind is ChannelKind.VALUE:
            return raw, (node.level, f"{owner.__name__}.{node.field}")
        materialized = _materialize(
            param, channel.kind, raw, anchor, world, rng,
        )
        if materialized is not None:
            return materialized, (node.level,
                                  f"{owner.__name__}.{node.field}")
    return inherited, inherited_source


def _link_object(
    objects: tuple[BaseModel, ...] | list[BaseModel],
    owner: type[BaseModel],
) -> BaseModel | None:
    for obj in objects or ():
        if isinstance(obj, owner):
            return obj
    return None


def _materialize(param, kind, raw, anchor, world, rng):
    if param is not ECONOMIC_TIER:
        raise ValueError(
            f"no materialize bound for param {param.field!r} kind={kind}"
        )
    return materialize_tier_input(world, kind, raw, anchor, rng)


def _apply_fold(param, level, objects, resolved, world):
    """``Cascade.fold`` binding — the per-param derived resolver that
    sits between the authored chain and the domain default, for params
    whose semantics is not pure first-non-null (tz_cascade_context §3,
    cascade-migration M10). Bound by identity, like ``_materialize``
    and ``_resolve_default`` — no callable lives in dataModel."""
    if param is DOMINANT_MATERIAL:
        picked = fold_dominant_material(world, objects, resolved)
        if picked is None:
            return None, None
        return picked, (level, f"fold:{param.fold}")
    raise ValueError(f"no fold bound for param {param.field!r}")


def _resolve_default(param: Cascade, world):
    """Domain default through the POJO policy; the engine logs the
    fallback (cascadeLog) — REGISTRY_MEDIAN warns once per chain
    (missing after the whole cascade = caller bug)."""
    if param is ECONOMIC_TIER:
        if world is None:
            raise ValueError(
                "economic_tier: no cascade value and no world for "
                "the registry median"
            )
        return economic_tiers(world).resolve_default(param.default)
    if param is CITY_SIZE:
        # Canonical rank (dataModel policy, not world registry).
        return WorldSettlementSizeRegistry.default_system_size()
    if param is SETTLEMENT_DENSITY:
        # Canonical enum default (dataModel policy, not a literal).
        return DistrictDensity.default()
    if param is WALL_MATERIAL:
        # Canonical construction default (dataModel policy, M9).
        return CONSTRUCTION_MATERIAL_DEFAULTS.wall
    if param is FLOOR_MATERIAL:
        return CONSTRUCTION_MATERIAL_DEFAULTS.floor
    if param is DOMINANT_MATERIAL:
        # Canonical construction default (dataModel policy, M10).
        return CONSTRUCTION_MATERIAL_DEFAULTS.dominant
    raise ValueError(
        f"no default policy bound for param {param.field!r}"
    )
