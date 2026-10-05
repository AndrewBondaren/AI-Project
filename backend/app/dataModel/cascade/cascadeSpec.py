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

from pydantic import BaseModel


class ScopeAxis(StrEnum):
    """An axis of scope tags for one domain (locations, factions…).

    Members are semantic tags, not a fixed ordering — the legal nesting
    shape is the per-axis containment DAG (``containment_parents``);
    runtime order comes from the actual ancestor chain the caller walks
    (tz_cascade_context §2 — целевая модель scope). Declaration order
    still gives ``rank`` for axes that stay linear.

    Every domain enum inherits this mixin instead of a shared closed
    list.
    """

    @property
    def rank(self) -> int:
        return tuple(type(self)).index(self)

    @classmethod
    def containment_parents(cls) -> dict["ScopeAxis", frozenset["ScopeAxis"]]:
        """may-contain DAG: member → directly containing members.

        Default = the linear axis (each member under the previous).
        Domains with branched nesting (locations: wilderness and
        settlement branches, dungeon under city or forest) override
        with their DAG.
        """
        members = tuple(cls)
        return {
            member: frozenset({members[index - 1]}) if index else frozenset()
            for index, member in enumerate(members)
        }

    def scope_descendant_of(self, ancestor: "ScopeAxis") -> bool:
        """Strict descendant in the containment DAG — deeper in the
        scope chain, possibly skipping tags (a tavern under a forest
        skips district/area, which the enum order would have rejected).
        """
        parents = type(self).containment_parents()
        seen: set[ScopeAxis] = set()
        stack = list(parents.get(self, ()))
        while stack:
            current = stack.pop()
            if current is ancestor:
                return True
            if current not in seen:
                seen.add(current)
                stack.extend(parents.get(current, ()))
        return False

    def scope_adjacent(self, other: "ScopeAxis") -> bool:
        """Same tag or containment-adjacent in either direction —
        the verifier's edge-legality rule (replaces rank-adjacency)."""
        if self is other:
            return True
        parents = type(self).containment_parents()
        return (
            self in parents.get(other, ())
            or other in parents.get(self, ())
        )


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
    # The canonical default itself for CANONICAL_DEFAULT — a value
    # pulled from the domain POJO at declaration (cascadeParams), never
    # a literal (dataModel-no-hardcode). Verified against the context
    # field's annotation — ``model_copy`` does not re-validate.
    default_value: object | None = None
    # Named world registry for REGISTRY_MEDIAN (e.g. "economic_tiers") —
    # a name bound by the application engine's registry table.
    default_registry: str | None = None
    # Optional restriction to a subset of levels for future parameters.
    levels: tuple[ScopeAxis, ...] | None = None
    # Expected field types for materialize-input kinds — the domain
    # declares what its channels carry (e.g. RANGE → EconomicTierRange).
    # Kinds without an entry accept str-compatible wire keys (BAND).
    input_types: tuple[tuple[ChannelKind, type], ...] = ()


@dataclass(frozen=True)
class CascadeLink:
    """One node pointer: a field of a model at a level.

    ``model=None`` — the declaring model itself (self-edge).
    """

    model: type[BaseModel] | None
    field: str
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
