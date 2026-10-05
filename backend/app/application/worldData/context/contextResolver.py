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
from app.dataModel.cascade.cascadeGraph import (
    check_link,
    ordered_chain,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    ChannelKind,
    DefaultPolicy,
)
from app.dataModel.locations.context.locationContext import LocationContext


# Cascade-annotated fields of the context model — computed once: the
# model is frozen, the scan would be identical on every ``extend()``.
_CASCADE_FIELDS: tuple[tuple[str, Cascade], ...] = tuple(
    (name, param)
    for name, info in LocationContext.model_fields.items()
    for param in (
        next(
            (m for m in info.metadata if isinstance(m, Cascade)),
            None,
        ),
    )
    if param is not None
)


# Resolver bindings — the single place where names declared on
# ``Cascade`` (tz_cascade_context §3) meet their callables. Domain
# callables live in their own modules; the engine holds pointers, not
# logic.
_MATERIALIZE = {
    "economic_tier": materialize_tier_input,
}
_FOLDS = {
    "dominant_material": fold_dominant_material,
}
_REGISTRIES = {
    "economic_tiers": economic_tiers,
}


def _check_bindings() -> None:
    """Every resolver/registry name declared on a ``Cascade`` param of
    the context model must resolve to a callable — declaration and
    binding table are two facts that must not silently disagree."""
    for _name, param in _CASCADE_FIELDS:
        for name, table, what in (
            (param.materialize, _MATERIALIZE, "materialize"),
            (param.fold, _FOLDS, "fold"),
            (param.default_registry, _REGISTRIES, "default_registry"),
        ):
            if name is not None and name not in table:
                raise ValueError(
                    f"{what} {name!r} of param {param.field!r} "
                    "has no binding"
                )


_check_bindings()


def extend(
    ctx: LocationContext, *links: Link, rng: Random | None = None,
) -> LocationContext:
    """Add one scope level of links; return a new resolved context."""
    level = _check_level(ctx, links)
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
    params: dict[str, tuple] = {}

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
                    fold = _FOLDS.get(param.fold)
                    if fold is None:
                        raise ValueError(
                            f"no fold bound for param {param.field!r}"
                        )
                    picked = fold(ctx._world, objects, update)
                    if picked is not None:
                        value, source = (
                            picked, (level, f"fold:{param.fold}"),
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
        params[name] = (value, inherited_source, source)

    # Fold params resolve in a second pass — their resolver reads this
    # level's freshly resolved values (e.g. the dominant-material pick
    # uses the tier resolved at this same scope).
    for name, param in _CASCADE_FIELDS:
        if param.fold is None:
            _resolve_field(name, param)
    for name, param in _CASCADE_FIELDS:
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
        resolver = (
            _MATERIALIZE.get(param.materialize)
            if param.materialize
            else None
        )
        if resolver is None:
            raise ValueError(
                f"no materialize bound for param {param.field!r} "
                f"kind={channel.kind}"
            )
        materialized = resolver(world, channel.kind, raw, anchor, rng)
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


def _resolve_default(param: Cascade, world):
    """Domain default through the declared policy: canonical values are
    declared on the param (``default_value``), registry policies resolve
    through the named world registry (``default_registry`` →
    ``_REGISTRIES``). The engine logs the fallback (cascadeLog) —
    REGISTRY_MEDIAN warns once per chain (missing after the whole
    cascade = caller bug)."""
    if param.default is DefaultPolicy.CANONICAL_DEFAULT:
        return param.default_value
    if param.default is DefaultPolicy.REGISTRY_MEDIAN:
        if world is None:
            raise ValueError(
                f"{param.field}: no cascade value and no world for "
                "the registry median"
            )
        accessor = _REGISTRIES.get(param.default_registry or "")
        if accessor is None:
            raise ValueError(
                f"no registry bound for param {param.field!r} "
                f"({param.default_registry!r})"
            )
        return accessor(world).resolve_default(param.default)
    raise ValueError(
        f"no default policy bound for param {param.field!r}"
    )


def _check_level(ctx: LocationContext, links: tuple[Link, ...]):
    """All links carry exactly one scope level, strictly below
    ``ctx.level`` and adjacent to it on the same axis."""
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
    return level
