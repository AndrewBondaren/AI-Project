"""Field metadata; resolver implementations belong to application (§3).

The cascade contract is a **doubly-linked list of fields**, declared on
the source POJO fields themselves in the same style as wire policies
(``DefaultOnWire``):

- ``Cascade`` — the parameter object, declared once in ``cascadeParams``;
  context fields and source channels reference it by **identity**;
- ``CascadeChannel(param, level, above, below, kind)`` — ``Annotated``
  metadata on a source field: "this field feeds ``param`` at ``level``";
- ``FieldRef(model_supplier, selector)`` — typed source field selection,
  declared outside ``Annotated`` so static checkers inspect the selector;
- ``CascadeLink(ref, level)`` — a typed pointer to a neighbour node
  (like ``prev``/``next`` in a linked list).

Each edge is declared **exactly once**, on the side whose module may
import the neighbour without a cycle — the ORM ``backref`` convention:
the verifier materializes the reverse direction, so in the checked
graph every node has both neighbours. (Declaring both sides in literals
would mean two independent facts that can silently disagree; SQLAlchemy
``back_populates`` gets away with it only via lazy string refs, which
this contract deliberately avoids.) Model suppliers are evaluated after
classes exist, so self-links use the same typed API as external links.

Scope axes are per-domain enums on the ``ScopeAxis`` mixin
(``ScopeLevel`` for the location hierarchy, a future ``FactionScope``
for factions, …). The cascade is a mechanism on top of **any** axis:
a parameter binds to its axis via ``Cascade.axis``, and a channel
declared on a foreign axis is a contract error
(tz_cascade_context §2, master's clarification 2026-10-03).

This module holds only the declaration vocabulary. Introspection and
verification of the declared graph — ``cascade_channels``,
``check_link``, ``ordered_chain``, ``verify_cascade_contract`` — live in
``cascadeGraph``.
"""

from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class ScopeAxis(StrEnum):
    """An axis of scope tags for one domain (locations, factions…).

    Members identify scopes; cascade channel order is declared by
    field links, independently of enum declaration order or location
    containment. ``rank`` exposes declaration position for compatibility;
    the resolver derives its path from field links (tz_cascade_context §2, §4).

    Every domain enum inherits this mixin instead of a shared closed
    list.
    """

    @property
    def rank(self) -> int:
        return tuple(type(self)).index(self)


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


M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")


@dataclass(frozen=True)
class FieldRef(Generic[M, T]):
    """Statically checked direct field selection, with deferred model lookup."""

    model: Callable[[], type[M]]
    select: Callable[[M], T]


@dataclass(frozen=True)
class CascadeDefault:
    """Terminal fallback field on a caller-supplied source POJO.

    The field may be computed by its domain model; the cascade engine
    only reads it, without a registry-name or value table.
    """

    ref: FieldRef[Any, Any]


@dataclass(frozen=True)
class Cascade:
    """Cascade parameter — declared once in ``cascadeParams``, referenced
    by identity from the context field and every source channel."""

    field: str
    default: DefaultPolicy
    # The scope axis this parameter cascades along (e.g. ``ScopeLevel``
    # for the location hierarchy). Channels on a foreign axis are a
    # contract violation.
    axis: type[ScopeAxis]
    # Optional resolver name, bound by the application engine, never an
    # application callable imported into this dataModel contract.
    fold: str | None = None
    # Optional resolver name for materialize-input kinds (BAND/RANGE) —
    # bound by the application engine like ``fold``; required when the
    # param declares non-VALUE channels.
    materialize: str | None = None
    # Typed field reference, not a copied default value or registry name.
    default_source: CascadeDefault | None = None
    # Optional restriction to a subset of levels for future parameters.
    levels: tuple[ScopeAxis, ...] | None = None
    # Expected field types for materialize-input kinds — the domain
    # declares what its channels carry (e.g. RANGE → EconomicTierRange).
    # Kinds without an entry accept str-compatible wire keys (BAND).
    input_types: tuple[tuple[ChannelKind, type], ...] = ()


@dataclass(frozen=True)
class CascadeLink:
    """Typed declaration of a neighbouring field at a scope level."""

    ref: FieldRef[Any, Any]
    level: ScopeAxis


@dataclass(frozen=True)
class CascadeChannel:
    """Declared on a source POJO field: this field is a cascade channel.

    ``above`` — the node that overrides this field (deeper scope);
    ``below`` — the node this field overrides (shallower scope).
    """

    param: Cascade
    level: ScopeAxis
    above: CascadeLink | None = None
    below: CascadeLink | None = None
    kind: ChannelKind = ChannelKind.VALUE
