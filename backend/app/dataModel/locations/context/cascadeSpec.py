"""Field metadata; resolver implementations belong to application (§3).

The cascade contract is a **doubly-linked list of fields**, declared on
the source POJO fields themselves in the same style as wire policies
(``DefaultOnWire``):

- ``Cascade`` — the parameter object, declared once in ``cascadeParams``;
  context fields and source channels reference it by **identity**;
- ``CascadeChannel(param, level, above, below, kind)`` — ``Annotated``
  metadata on a source field: "this field feeds ``param`` at ``level``";
- ``CascadeLink(model, field, level)`` — a typed pointer to a neighbour
  node (like ``prev``/``next`` in a linked list).

Each edge is declared **exactly once**, on the side whose module may
import the neighbour without a cycle — the ORM ``backref`` convention:
the verifier materializes the reverse direction, so in the checked
graph every node has both neighbours. (Declaring both sides in literals
would mean two independent facts that can silently disagree; SQLAlchemy
``back_populates`` gets away with it only via lazy string refs, which
this contract deliberately avoids.) ``model=None`` in a link means the
declaring model — a class cannot reference itself inside its own body.

``CascadeLevel`` stays a pure ordering axis — it knows nothing about
which models feed which level (tz_cascade_context §2, master's
clarification 2026-10-03).
"""

from dataclasses import dataclass
from enum import StrEnum
from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.locations.context.cascadeLevel import CascadeLevel
from app.dataModel.shared.ranges import EconomicTierRange


class DefaultPolicy(StrEnum):
    REGISTRY_MEDIAN = "registry_median"
    CANONICAL_DEFAULT = "canonical_default"
    NONE_IS_ERROR = "none_is_error"


class ChannelKind(StrEnum):
    """How a source field feeds the cascade parameter."""

    VALUE = "value"
    """Direct authored value of the parameter (tier key, material key…)."""
    BAND = "band"
    """Band input — materialize resolves it into a value (tier band → tier)."""
    RANGE = "range"
    """Range input — materialize resolves nearest-to-anchor / rng inside it."""


@dataclass(frozen=True)
class Cascade:
    """Cascade parameter — declared once in ``cascadeParams``, referenced
    by identity from the context field and every source channel."""

    field: str
    default: DefaultPolicy
    # Optional resolver name, bound by the application engine, never an
    # application callable imported into this dataModel contract.
    fold: str | None = None
    # Optional restriction to a subset of levels for future parameters.
    levels: tuple[CascadeLevel, ...] | None = None


@dataclass(frozen=True)
class CascadeLink:
    """One node pointer: a field of a model at a level.

    ``model=None`` — the declaring model itself (self-edge).
    """

    model: type[BaseModel] | None
    field: str
    level: CascadeLevel


@dataclass(frozen=True)
class CascadeChannel:
    """Declared on a source POJO field: this field is a cascade channel.

    ``above`` — the node that overrides this field (deeper scope);
    ``below`` — the node this field overrides (shallower scope).
    """

    param: Cascade
    level: CascadeLevel
    above: CascadeLink | None = None
    below: CascadeLink | None = None
    kind: ChannelKind = ChannelKind.VALUE


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
    level: CascadeLevel | None = None,
) -> tuple[tuple[str, CascadeChannel], ...]:
    """Channels declared on ``model``, optionally filtered."""
    return tuple(
        (name, channel)
        for name, channel in _channels_of(model)
        if (param is None or channel.param is param)
        and (level is None or channel.level is level)
    )


def check_link(level: CascadeLevel, obj: object) -> None:
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
    if channel.kind is ChannelKind.RANGE:
        return _mentions(annotation, EconomicTierRange)
    return _is_str_compatible(annotation)


def _describe(link: CascadeLink) -> str:
    name = link.model.__name__ if link.model else "?"
    return f"{name}.{link.field}@{link.level.value}"


def verify_cascade_contract(context_model: type[BaseModel]) -> None:
    """Verify the linked list for every param declared on the context.

    For each ``Cascade`` param: every declared link resolves to a real
    field carrying a channel for the same param at the linked level
    (name check); field types are kind-compatible (type check); edges
    form a single continuous doubly-linked chain — exactly one top and
    one bottom, no node with two neighbours on a side, no orphans; an
    edge may connect only same-level or rank-adjacent nodes; every
    non-world level is covered; ``param.field`` exists on a source.
    """
    errors: list[str] = []
    params = {
        meta
        for info in context_model.model_fields.values()
        for meta in info.metadata
        if isinstance(meta, Cascade)
    }
    # (param, node) -> channel ; node = CascadeLink with resolved model
    nodes: dict[tuple[Cascade, CascadeLink], CascadeChannel] = {}
    owners: dict[tuple[Cascade, CascadeLink], type[BaseModel]] = {}
    for model in _source_models():
        for field, channel in _channels_of(model):
            key = (channel.param, CascadeLink(model, field, channel.level))
            if key in nodes:
                errors.append(
                    f"{model.__name__}.{field}: duplicate channel for "
                    f"level {channel.level.value}"
                )
                continue
            nodes[key] = channel
            owners[key] = model
    for param in params:
        chain_nodes = {
            link: channel
            for (p, link), channel in nodes.items() if p is param
        }
        if not chain_nodes:
            errors.append(
                f"param field='{param.field}': no channel declares it"
            )
            continue
        # Collect declared edges, normalized as (upper, lower) node keys.
        edges: dict[tuple[CascadeLink, CascadeLink], CascadeLink] = {}
        above_of: dict[CascadeLink, CascadeLink] = {}
        below_of: dict[CascadeLink, CascadeLink] = {}
        for link, channel in chain_nodes.items():
            owner = owners[(param, link)]
            node = _describe(link)
            if not _field_type_ok(owner, link.field, channel):
                errors.append(
                    f"{node}: channel kind={channel.kind} incompatible "
                    "with field type"
                )
            for side, edge in (
                ("above", channel.above), ("below", channel.below),
            ):
                if edge is None:
                    continue
                target_model = edge.model or owner
                target_fields = getattr(target_model, "model_fields", {})
                if edge.field not in target_fields:
                    errors.append(
                        f"{node}: {side} → {_describe(CascadeLink(target_model, edge.field, edge.level))} "
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
                pair = (
                    (target_key, link) if side == "above" else (link, target_key)
                )
                edges[pair] = link
        for upper, lower in edges:
            if lower in above_of and above_of[lower] != upper:
                errors.append(
                    f"{_describe(lower)}: two above neighbours "
                    f"{_describe(above_of[lower])} and {_describe(upper)}"
                )
            if upper in below_of and below_of[upper] != lower:
                errors.append(
                    f"{_describe(upper)}: two below neighbours "
                    f"{_describe(below_of[upper])} and {_describe(lower)}"
                )
            above_of[lower] = upper
            below_of[upper] = lower
            gap = upper.level.rank - lower.level.rank
            if gap < 0 or gap > 1:
                errors.append(
                    f"edge {_describe(upper)} → {_describe(lower)} "
                    "skips a level or points upward"
                )
        tops = [link for link in chain_nodes if link not in above_of]
        bottoms = [link for link in chain_nodes if link not in below_of]
        if len(tops) != 1 or len(bottoms) != 1:
            errors.append(
                f"param field='{param.field}': chain must have exactly "
                f"one top and one bottom, got "
                f"{len(tops)}/{len(bottoms)}"
            )
        else:
            visited: set[CascadeLink] = set()
            cursor = tops[0]
            while cursor not in visited:
                visited.add(cursor)
                nxt = below_of.get(cursor)
                if nxt is None:
                    break
                if nxt not in chain_nodes:
                    break
                cursor = nxt
            if visited != set(chain_nodes):
                missing = set(chain_nodes) - visited
                errors.append(
                    f"param field='{param.field}': chain broken — "
                    f"unreachable nodes: "
                    f"{sorted(_describe(l) for l in missing)}"
                )
        covered = {link.level for link in chain_nodes}
        expected = param.levels or (set(CascadeLevel) - {CascadeLevel.WORLD})
        missing_levels = expected - covered
        if missing_levels:
            errors.append(
                f"param field='{param.field}': levels without channel: "
                f"{sorted(level.value for level in missing_levels)}"
            )
        if not any(
            param.field in owners[(param, link)].model_fields
            for link in chain_nodes
        ):
            errors.append(
                f"param field='{param.field}': canonical field exists on "
                "no source model"
            )
    if errors:
        raise ValueError("cascade contract violated: " + "; ".join(errors))
