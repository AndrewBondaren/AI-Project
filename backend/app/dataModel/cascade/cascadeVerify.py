"""Whole-graph contract verification — tz_cascade_context §2, §3.

``verify_cascade_contract(context_model)`` checks every ``Cascade``
param declared on the context against the channel graph materialized by
``cascadeGraph``. Run it where the contract must hold (contract tests,
import validation) — the engine walks only a verified chain.
"""

from pydantic import BaseModel

from app.dataModel.cascade.cascadeGraph import (
    CascadeNode,
    bind_field,
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
    side, no orphans; channel order comes from the declared links,
    not scope containment or enum rank; declared levels are covered;
    ``param.field`` exists on a source.
    """
    errors: list[str] = []
    params = {
        meta: name
        for name, info in context_model.model_fields.items()
        for meta in info.metadata
        if isinstance(meta, Cascade)
    }
    # (param, node) -> channel ; node = CascadeNode with resolved model
    nodes: dict[tuple[Cascade, CascadeNode], CascadeChannel] = {}
    for model in _source_models():
        for field, channel in _channels_of(model):
            key = (channel.param, CascadeNode(model, field, channel.level))
            if key in nodes:
                errors.append(
                    f"{model.__name__}.{field}: duplicate channel for "
                    f"level {channel.level.value}"
                )
                continue
            nodes[key] = channel
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
        above_of: dict[CascadeNode, CascadeNode] = {}
        below_of: dict[CascadeNode, CascadeNode] = {}
        for link, channel in chain_nodes.items():
            owner = link.model
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
        edges, edge_errors = _declared_edges(chain_nodes)
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
        tops = [link for link in chain_nodes if link not in above_of]
        bottoms = [link for link in chain_nodes if link not in below_of]
        if len(tops) != 1 or len(bottoms) != 1:
            errors.append(
                f"param field='{param.field}': chain must have exactly "
                f"one top and one bottom, got "
                f"{len(tops)}/{len(bottoms)}"
            )
        else:
            visited: set[CascadeNode] = set()
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
            param.field in link.model.model_fields
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
    chain_nodes: dict[CascadeNode, CascadeChannel],
) -> list[str]:
    """A param's declaration must be self-contained: the default is a
    typed field of a source POJO; materialize inputs carry a declared resolver
    name — no param-specific branch may live in the engine."""
    label = f"param field='{param.field}'"
    errors: list[str] = []
    source = param.default_source
    if param.default is DefaultPolicy.NONE_IS_ERROR:
        if source is not None:
            errors.append(f"{label}: NONE_IS_ERROR forbids default_source")
    elif source is None:
        errors.append(f"{label}: {param.default.value} requires default_source")
    else:
        try:
            bound = bind_field(source.ref, computed=True)
        except ValueError as exc:
            errors.append(f"{label}: default_source {exc}")
        else:
            if _base_types(bound.model, bound.field) != _base_types(context_model, ctx_field):
                errors.append(f"{label}: default_source field type incompatible with context")
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

