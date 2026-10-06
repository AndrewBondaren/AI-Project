"""Generic cascade resolver — tz_cascade_context §4.

``extend()`` derives scope boundaries from declared field links and
binds each parameter's linked list to the accumulated source POJOs.
One iterator walks that runtime chain in declared priority order.
Ancestor node results are snapshots: only new scope nodes are evaluated,
so materialization never re-rolls when the context is extended.

One resolution per scope: the caller supplies the rng for the scope
(``entity_rng(world_uid, UidKind.CASCADE, scope=scope_uid, param=…)``); a materialize
channel that needs it (no anchor) requires it — missing rng is a
caller bug, never a silent skip.
"""

from functools import lru_cache
from random import Random

from pydantic import BaseModel

from app.application.worldData.context.cascadeLink import Link
from app.application.worldData.context.cascadeLog import (
    log_default_applied,
    log_scope_resolve,
)
from app.application.worldData.context.runtimeChain import bind_chain
from app.application.worldData.generators.utils.economicTierBands import (
    materialize_tier_input,
)
from app.application.worldData.generators.utils.materialResolver import (
    fold_dominant_material,
)
from app.dataModel.cascade.cascadeGraph import (
    check_link,
    ordered_scopes,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    ChannelKind,
)
from app.dataModel.locations.context.locationContext import LocationContext


@lru_cache
def _cascade_fields(model: type[BaseModel]) -> tuple[tuple[str, Cascade], ...]:
    """Discover parameters on the calling context, without a field table."""
    return tuple(
        (name, meta)
        for name, info in model.model_fields.items()
        for meta in info.metadata
        if isinstance(meta, Cascade)
    )


def scope_sequence(ctx: LocationContext):
    """Declared scope path shared by the resolver and empty-scope callers."""
    return ctx._scope_path or ordered_scopes(
        tuple(param for _, param in _cascade_fields(type(ctx))), ctx.level,
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


def _check_bindings(model: type[BaseModel]) -> None:
    """Every operation name declared on a ``Cascade`` param of
    the context model must resolve to a callable — declaration and
    binding table are two facts that must not silently disagree."""
    for _name, param in _cascade_fields(model):
        for name, table, what in (
            (param.materialize, _MATERIALIZE, "materialize"),
            (param.fold, _FOLDS, "fold"),
        ):
            if name is not None and name not in table:
                raise ValueError(
                    f"{what} {name!r} of param {param.field!r} "
                    "has no binding"
                )


_check_bindings(LocationContext)


def extend(
    ctx: LocationContext, *links: Link, rng: Random | None = None,
) -> LocationContext:
    """Add one scope level of links; return a new resolved context."""
    fields = _cascade_fields(type(ctx))
    _check_bindings(type(ctx))
    path = scope_sequence(ctx)
    level = _check_level(ctx, links, path)
    objects = []
    for link in links:
        if link.obj is None:
            continue
        check_link(level, link.obj)
        objects.append(link.obj)

    stored = dict(ctx._links)
    stored[level] = tuple(objects)
    node_results = dict(ctx._node_results)

    provenance = dict(ctx.provenance)
    update = {"level": level}
    params: dict[str, tuple] = {}

    def _resolve_field(name: str, param: Cascade) -> None:
        inherited_source = ctx.provenance.get(name)
        value, source = _resolve(
            param, level, stored, node_results, getattr(ctx, name),
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
                    value = _resolve_default(param, ctx._default_sources)
                    source = (path[0],
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
    for name, param in fields:
        if param.fold is None:
            _resolve_field(name, param)
    for name, param in fields:
        if param.fold is not None:
            _resolve_field(name, param)
    update["provenance"] = provenance
    new_ctx = ctx.model_copy(update=update)
    new_ctx._world = ctx._world
    new_ctx._links = stored
    new_ctx._scope_path = path
    new_ctx._node_results = node_results
    log_scope_resolve(
        level=level.value,
        objects=[type(obj).__name__ for obj in objects],
        params=params,
    )
    return new_ctx


def _is_default(source) -> bool:
    return bool(source) and source[1].startswith("default:")


def _resolve(param, level, sources, results, inherited, inherited_source,
             world, rng):
    """Walk one bound chain; reuse ancestor snapshots, evaluate new nodes."""
    # A provisional default is not an authored anchor — a deeper
    # materialize rolls instead of clamping to the median.
    anchor = None if _is_default(inherited_source) else inherited
    for bound in bind_chain(param, sources):
        key = (param, bound.node)
        if bound.node.level is level and key not in results:
            raw = (
                getattr(bound.obj, bound.node.field)
                if bound.obj is not None else None
            )
            value = raw
            if raw is not None and bound.channel.kind is not ChannelKind.VALUE:
                resolver = _MATERIALIZE.get(param.materialize)
                if resolver is None:
                    raise ValueError(
                        f"no materialize bound for param {param.field!r} "
                        f"kind={bound.channel.kind}"
                    )
                value = resolver(world, bound.channel.kind, raw, anchor, rng)
            results[key] = (value, bound.source if value is not None else None)
        value, source = results.get(key, (None, None))
        if value is not None:
            return value, source
    return inherited, inherited_source


def _resolve_default(param: Cascade, sources: tuple[BaseModel, ...]):
    """Read the declared terminal POJO field; domain values stay in POJOs."""
    pointer = param.default_source
    if pointer is None:
        raise ValueError(f"{param.field}: no value after the cascade")
    matches = [obj for obj in sources if isinstance(obj, pointer.model)]
    if len(matches) != 1:
        raise ValueError(
            f"{param.field}: expected one default source {pointer.model.__name__}, "
            f"got {len(matches)}"
        )
    value = getattr(matches[0], pointer.field)
    if value is None:
        raise ValueError(f"{param.field}: terminal default source returned None")
    return value


def _check_level(ctx: LocationContext, links: tuple[Link, ...], path):
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
    if level not in path:
        raise ValueError(f"level {level.value} has no declared cascade boundary")
    current_index = path.index(ctx.level)
    next_index = path.index(level)
    if next_index <= current_index:
        raise ValueError(
            f"level {level.value} is not strictly below "
            f"{ctx.level.value}"
        )
    if next_index > current_index + 1:
        raise ValueError(
            f"level {level.value} skips a level after "
            f"{ctx.level.value}"
        )
    return level
