"""Channel graph: introspection and ordering.

The declaration vocabulary lives in ``cascadeSpec``
(``Cascade``/``CascadeChannel``/``CascadeLink``). This module walks the
declared metadata: ``cascade_channels`` reads a model's channels,
``check_link`` validates a link object, ``_declared_edges`` materializes
the reverse direction of each declared edge and ``ordered_chain``
returns the chain top→bottom — the application engine's roadmap.
Whole-graph verification lives in ``cascadeVerify``
(tz_cascade_context §2).
"""

from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    CascadeChannel,
    CascadeLink,
    ChannelKind,
    ScopeAxis,
)


def _channels_of(model: type[BaseModel]) -> list[tuple[str, CascadeChannel]]:
    found: list[tuple[str, CascadeChannel]] = []
    for name, info in model.model_fields.items():
        for meta in info.metadata:
            if isinstance(meta, CascadeChannel):
                found.append((name, meta))
    return found


def cascade_channels(
    model: type[BaseModel],
    param: Cascade | None = None,
    level: ScopeAxis | None = None,
) -> tuple[tuple[str, CascadeChannel], ...]:
    """Channels declared on ``model``, optionally filtered."""
    return tuple(
        (name, channel)
        for name, channel in _channels_of(model)
        if (param is None or channel.param is param)
        and (level is None or channel.level is level)
    )


def check_link(level: ScopeAxis, obj: object) -> None:
    """Type-bound link contract — the object's type must declare a
    channel for ``level``. No isinstance table: a new POJO becomes a
    valid link by annotating a field."""
    if not cascade_channels(type(obj), level=level):
        raise TypeError(
            f"{type(obj).__name__} declares no cascade channel "
            f"for level {level.value}"
        )


def _source_models() -> set[type[BaseModel]]:
    """All loaded POJOs declaring at least one ``CascadeChannel``."""
    seen: set[type[BaseModel]] = set()
    stack = list(BaseModel.__subclasses__())
    while stack:
        model = stack.pop()
        if model in seen:
            continue
        seen.add(model)
        stack.extend(model.__subclasses__())
    return {model for model in seen if _channels_of(model)}


def _resolve_alias(annotation: object) -> object:
    """Peel PEP 695 ``TypeAliasType`` (e.g. ``EconomyTierKey``)."""
    while type(annotation).__name__ == "TypeAliasType":
        annotation = annotation.__value__
    return annotation


def _union_args(annotation: object) -> tuple[object, ...]:
    annotation = _resolve_alias(annotation)
    if get_origin(annotation) in (Union, UnionType):
        return get_args(annotation)
    return (annotation,)


def _is_str_compatible(annotation: object) -> bool:
    for arg in _union_args(annotation):
        inner = get_origin(_resolve_alias(arg)) or _resolve_alias(arg)
        if isinstance(inner, type) and issubclass(inner, str):
            return True
    return False


def _mentions(annotation: object, expected: type) -> bool:
    return any(
        (get_origin(_resolve_alias(arg)) or _resolve_alias(arg)) is expected
        for arg in _union_args(annotation)
    )


def _field_type_ok(
    model: type[BaseModel], field: str, channel: CascadeChannel,
) -> bool:
    annotation = unwrap_wire_type(model.model_fields[field].annotation)
    expected = dict(channel.param.input_types).get(channel.kind)
    if expected is None:
        # VALUE/BAND — a wire key, str-compatible (RegistryKey etc.).
        return _is_str_compatible(annotation)
    return _mentions(annotation, expected)


def _describe(link: CascadeLink) -> str:
    name = link.model.__name__ if link.model else "?"
    return f"{name}.{link.field}@{link.level.value}"


def _base_types(model: type[BaseModel], field: str) -> frozenset:
    """Normalized field types for edge-end comparison: wire policies
    unwrapped, aliases peeled, union members reduced to their origin,
    ``None`` dropped."""
    if field in model.model_fields:
        annotation = model.model_fields[field].annotation
    else:
        annotation = model.model_computed_fields[field].return_type
    annotation = unwrap_wire_type(annotation)
    found = set()
    for arg in _union_args(annotation):
        inner = get_origin(_resolve_alias(arg)) or _resolve_alias(arg)
        if inner is not type(None):
            found.add(inner)
    return frozenset(found)


def _type_names(types: frozenset) -> str:
    return " | ".join(
        sorted(getattr(t, "__name__", str(t)) for t in types)
    )


def _declared_edges(
    chain_nodes: dict[CascadeLink, CascadeChannel],
    owners: dict[CascadeLink, type[BaseModel]],
) -> tuple[set[tuple[CascadeLink, CascadeLink]], list[str]]:
    """Normalize declared links into ``(upper, lower)`` edge pairs.

    The reverse direction of each declared edge is materialized here —
    the checked graph has both neighbours for every node.
    """
    edges: set[tuple[CascadeLink, CascadeLink]] = set()
    errors: list[str] = []
    for link, channel in chain_nodes.items():
        owner = owners[link]
        node = _describe(link)
        for side, edge in (
            ("above", channel.above), ("below", channel.below),
        ):
            if edge is None:
                continue
            target_model = edge.model or owner
            if edge.field not in getattr(target_model, "model_fields", {}):
                errors.append(
                    f"{node}: {side} → "
                    f"{_describe(CascadeLink(target_model, edge.field, edge.level))} "
                    f"— no such field on {target_model.__name__}"
                )
                continue
            target_key = CascadeLink(target_model, edge.field, edge.level)
            if target_key not in chain_nodes:
                errors.append(
                    f"{node}: {side} → {_describe(target_key)} "
                    "— target declares no channel for this param "
                    "at that level"
                )
                continue
            edges.add(
                (target_key, link) if side == "above" else (link, target_key)
            )
    for upper, lower in edges:
        # Kind-aware end types (tz §2): two VALUE ends carry the same
        # base type; BAND/RANGE ends are materialize inputs whose field
        # type is bound to the kind, not to the neighbour's.
        if (
            chain_nodes[upper].kind is ChannelKind.VALUE
            and chain_nodes[lower].kind is ChannelKind.VALUE
        ):
            upper_types = _base_types(owners[upper], upper.field)
            lower_types = _base_types(owners[lower], lower.field)
            if upper_types != lower_types:
                errors.append(
                    f"edge {_describe(upper)} → {_describe(lower)}: "
                    f"VALUE ends declare different types "
                    f"({_type_names(upper_types)} vs "
                    f"{_type_names(lower_types)})"
                )
    return edges, errors


def ordered_chain(
    param: Cascade,
) -> tuple[tuple[type[BaseModel], CascadeLink, CascadeChannel], ...]:
    """Chain nodes ordered top→bottom — the engine's roadmap.

    Returns ``(owner_model, node, channel)`` triples. Raises
    ``ValueError`` on a broken chain — the engine walks only a
    verified graph.
    """
    chain_nodes: dict[CascadeLink, CascadeChannel] = {}
    owners: dict[CascadeLink, type[BaseModel]] = {}
    for model in _source_models():
        for field, channel in _channels_of(model):
            if channel.param is not param:
                continue
            link = CascadeLink(model, field, channel.level)
            chain_nodes.setdefault(link, channel)
            owners.setdefault(link, model)
    edges, errors = _declared_edges(chain_nodes, owners)
    above_of: dict[CascadeLink, CascadeLink] = {}
    below_of: dict[CascadeLink, CascadeLink] = {}
    for upper, lower in edges:
        if lower in above_of and above_of[lower] != upper:
            errors.append(f"{_describe(lower)}: two above neighbours")
        if upper in below_of and below_of[upper] != lower:
            errors.append(f"{_describe(upper)}: two below neighbours")
        above_of[lower] = upper
        below_of[upper] = lower
    tops = [link for link in chain_nodes if link not in above_of]
    bottoms = [link for link in chain_nodes if link not in below_of]
    if errors or len(tops) != 1 or len(bottoms) != 1:
        raise ValueError(
            "cascade chain is broken: "
            + "; ".join(errors or ["no unique top and bottom"])
        )
    order: list[CascadeLink] = []
    cursor = tops[0]
    while cursor not in order:
        order.append(cursor)
        nxt = below_of.get(cursor)
        if nxt is None or nxt not in chain_nodes:
            break
        cursor = nxt
    if len(order) != len(chain_nodes):
        raise ValueError(
            "cascade chain is broken: unreachable nodes "
            + ", ".join(
                _describe(link) for link in chain_nodes if link not in order
            )
        )
    return tuple(
        (owners[link], link, chain_nodes[link]) for link in order
    )


def ordered_scopes(
    params: tuple[Cascade, ...], root: ScopeAxis,
) -> tuple[ScopeAxis, ...]:
    """Derive scope boundaries from the declared field chains.

    Chains run override→fallback; scope propagation runs in the reverse
    direction. Parameters with narrower coverage contribute constraints,
    not extra scopes. Ambiguous or contradictory declarations are errors;
    enum order never breaks a tie.
    """
    parents: dict[ScopeAxis, set[ScopeAxis]] = {root: set()}
    for param in params:
        if param.axis is not type(root):
            raise ValueError("cascade parameter is on a foreign axis")
        previous = None
        for _, node, _ in reversed(ordered_chain(param)):
            scope = node.level
            if type(scope) is not type(root):
                raise ValueError("cascade channel is on a foreign axis")
            parents.setdefault(scope, set())
            if scope is not root:
                parents[scope].add(root)
            if previous is not None and previous is not scope:
                parents[scope].add(previous)
            previous = scope
    result: list[ScopeAxis] = []
    while parents:
        ready = [scope for scope, dependencies in parents.items()
                 if not dependencies]
        if len(ready) != 1:
            raise ValueError(
                "cascade scope order is ambiguous or cyclic in declared links"
            )
        scope = ready[0]
        result.append(scope)
        del parents[scope]
        for dependencies in parents.values():
            dependencies.discard(scope)
    return tuple(result)
