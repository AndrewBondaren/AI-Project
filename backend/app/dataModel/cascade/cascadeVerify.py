"""Whole-graph contract verification — tz_cascade_context §2, §3.

``verify_cascade_contract(context_model)`` checks every ``Cascade``
param declared on the context against the channel graph materialized by
``cascadeGraph``. Run it where the contract must hold (contract tests,
import validation) — the engine walks only a verified chain.
"""

from enum import Enum

from pydantic import BaseModel

from app.dataModel.cascade.cascadeGraph import (
    _base_types,
    _channels_of,
    _declared_edges,
    _describe,
    _field_type_ok,
    _source_models,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    CascadeChannel,
    CascadeLink,
    ChannelKind,
    DefaultPolicy,
)


def verify_cascade_contract(context_model: type[BaseModel]) -> None:
    """Verify the linked list for every param declared on the context.

    For each ``Cascade`` param: every declared link resolves to a real
    field carrying a channel for the same param at the linked level
    (name check); field types are kind-compatible (type check); two
    ``VALUE`` ends of an edge declare the same base type, while
    ``BAND``/``RANGE`` ends are materialize inputs (kind-aware end
    types, tz §2); edges form a single continuous doubly-linked chain —
    exactly one top and one bottom, no node with two neighbours on a
    side, no orphans; an edge may connect only same-level or
    rank-adjacent nodes; every non-world level is covered;
    ``param.field`` exists on a source.
    """
    errors: list[str] = []
    params = {
        meta: name
        for name, info in context_model.model_fields.items()
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
    for param, ctx_field in params.items():
        chain_nodes = {
            link: channel
            for (p, link), channel in nodes.items() if p is param
        }
        errors.extend(
            _binding_errors(param, context_model, ctx_field, chain_nodes)
        )
        if not chain_nodes:
            errors.append(
                f"param field='{param.field}': no channel declares it"
            )
            continue
        # Declared edges normalized as (upper, lower) node keys.
        above_of: dict[CascadeLink, CascadeLink] = {}
        below_of: dict[CascadeLink, CascadeLink] = {}
        for link, channel in chain_nodes.items():
            owner = owners[(param, link)]
            node = _describe(link)
            if type(link.level) is not param.axis:
                errors.append(
                    f"{node}: channel on foreign axis "
                    f"{type(link.level).__name__} — param axis is "
                    f"{param.axis.__name__}"
                )
            if not _field_type_ok(owner, link.field, channel):
                errors.append(
                    f"{node}: channel kind={channel.kind} incompatible "
                    "with field type"
                )
        local_owners = {
            link: owners[(param, link)] for link in chain_nodes
        }
        edges, edge_errors = _declared_edges(chain_nodes, local_owners)
        errors.extend(edge_errors)
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
            if not upper.level.scope_adjacent(lower.level):
                errors.append(
                    f"edge {_describe(upper)} → {_describe(lower)} "
                    "connects scopes that may not neighbour "
                    "(scope-DAG, tz_cascade_context §2)"
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
        root = next(iter(param.axis))
        expected = (
            set(param.levels)
            if param.levels is not None
            else set(param.axis) - {root}
        )
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


def _binding_errors(
    param: Cascade,
    context_model: type[BaseModel],
    ctx_field: str,
    chain_nodes: dict[CascadeLink, CascadeChannel],
) -> list[str]:
    """A param's declaration must be self-contained: the default is a
    declared value (``default_value``) or a named registry
    (``default_registry``), materialize inputs carry a declared resolver
    name — no param-specific branch may live in the engine."""
    label = f"param field='{param.field}'"
    errors: list[str] = []
    if param.default is DefaultPolicy.CANONICAL_DEFAULT:
        if param.default_value is None:
            errors.append(
                f"{label}: CANONICAL_DEFAULT requires default_value"
            )
        elif not _default_value_ok(context_model, ctx_field, param):
            errors.append(
                f"{label}: default_value {param.default_value!r} "
                f"incompatible with context field '{ctx_field}' type"
            )
    elif param.default_value is not None:
        errors.append(
            f"{label}: default_value declared but policy is "
            f"{param.default.value}"
        )
    if param.default is DefaultPolicy.REGISTRY_MEDIAN:
        if param.default_registry is None:
            errors.append(
                f"{label}: REGISTRY_MEDIAN requires default_registry"
            )
    elif param.default_registry is not None:
        errors.append(
            f"{label}: default_registry declared but policy is "
            f"{param.default.value}"
        )
    has_materialize_inputs = any(
        channel.kind is not ChannelKind.VALUE
        for channel in chain_nodes.values()
    )
    if has_materialize_inputs and param.materialize is None:
        errors.append(
            f"{label}: non-VALUE channels require materialize name"
        )
    if not has_materialize_inputs and param.materialize is not None:
        errors.append(
            f"{label}: materialize declared but no BAND/RANGE channels"
        )
    return errors


def _default_value_ok(
    context_model: type[BaseModel], field: str, param: Cascade,
) -> bool:
    for base in _base_types(context_model, field):
        if not isinstance(base, type):
            continue
        # Enum fields require the real member — a literal string would
        # be a silent fork of the POJO default. Str-keyed aliases
        # (RegistryKey[X]) are runtime-indistinguishable, any str
        # qualifies.
        expected = (
            str
            if issubclass(base, str) and not issubclass(base, Enum)
            else base
        )
        if isinstance(param.default_value, expected):
            return True
    return False
