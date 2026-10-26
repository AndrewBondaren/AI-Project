"""Canonical library spec — domain declaration, the only registration path.

SoT: ``docs/tz_json_validation.md`` § «Единый движок canonical defaults»;
pack contract: ``docs/tz_template_library_packs.md`` §6.
A domain declares one ``CanonicalLibrarySpec``; the engine
(``canonicalLibrary.engine``) performs attach without knowing the domain.

Completeness cache contract — fixed declaration taken as input by the pack
plan B-2 (TZ §6):

- ``fullness`` = "all canonical UIDs are present" (plus membership for
  pack adapters). Positive fullness caching is forbidden: the only lawful
  mode is ``FullnessCacheMode.NONE`` — presence is re-checked on every
  ``ensure_canonical``, a deleted canonical UID is restored on the next
  call, and a non-empty table is never treated as complete. No "single
  row with the right ``source_file``" shortcut either.
- ``source`` = whether adapters may memoize the *validated snapshot*:
  ``NONE`` reloads and revalidates on every call; ``FINGERPRINT`` allows
  caching keyed by ``CanonicalSnapshot.fingerprint`` — the version token
  the source adapter computes from the declared source (manifest/files).
  Row presence is still re-checked on every attach.
- A failed attach marks nothing and may be retried; no cache may hide
  incompleteness.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.application.canonicalLibrary.adapters import (
        CanonicalPersistenceAdapter,
        CanonicalSourceAdapter,
    )


class CanonicalLibraryError(Exception):
    """Base error of the canonical-defaults engine."""


class CanonicalSpecError(CanonicalLibraryError):
    """Spec is incoherent or the operation does not match the declared scope."""


class CanonicalSourceError(CanonicalLibraryError):
    """Declared canonical source failed the engine-side contract checks."""


class CanonicalContractError(CanonicalLibraryError):
    """Adapter returned a result violating the engine contract."""


class CanonicalScope(StrEnum):
    """Where the canonical set lives."""

    WORLD = "world"  # registry inside the world bundle
    GLOBAL = "global"  # SQL library outside any world


class CanonicalAttachPolicy(StrEnum):
    """How canonical entries are attached."""

    # Merge raw wire fields before validation; persisted by the ordinary
    # world import. See ``canonicalLibrary.engine.canonical_merge``.
    WORLD_WIRE_OVERLAY = "world_wire_overlay"
    # Atomically insert missing canonical UIDs; existing rows (including
    # user overrides of canonical UIDs) are never replaced. See
    # ``canonicalLibrary.engine.ensure_canonical``.
    GLOBAL_FILL_MISSING = "global_fill_missing"


class FullnessCacheMode(StrEnum):
    """Where "library is complete" may be memoized — TZ §6."""

    # Re-check canonical UID presence on every attach. The only lawful
    # value: positive fullness caching is forbidden so that a deleted
    # canonical UID is restored on the next ``ensure_canonical``.
    NONE = "none"


class SourceCacheMode(StrEnum):
    """Whether the *validated source snapshot* may be cached."""

    NONE = "none"  # reload + revalidate the declared source every attach
    # Adapter may cache the validated snapshot keyed by the fingerprint
    # it reports in ``CanonicalSnapshot.fingerprint`` (manifest/files
    # version). Presence of rows is still re-checked every attach.
    FINGERPRINT = "fingerprint"


@dataclass(frozen=True)
class CanonicalCachePolicy:
    """Cache declaration of the domain — see module docstring for the contract."""

    fullness: FullnessCacheMode = FullnessCacheMode.NONE
    source: SourceCacheMode = SourceCacheMode.NONE


@dataclass(frozen=True)
class CanonicalLibrarySpec:
    """Immutable typed declaration of a canonical library domain.

    Fields by scope:

    - ``name`` — domain identifier for logs/errors (e.g. ``material_registry``,
      ``structure_templates``).
    - ``identity_field`` — world scope: wire key matching world rows to
      canonical rows; the domain reads it from the POJO
      ``CANONICAL_OVERLAY_ID_FIELD`` — never a duplicated literal.
      Global scope: canonical identity lives on ``CanonicalEntry.uid``
      (minted only via ``app.ids``).
    - ``world_canonical_rows`` — world scope: provider of canonical wire
      rows (``Mapping`` with ``identity_field``), e.g. POJO
      ``canonical_defaults()`` dumped to wire. Explicit declaration —
      no wildcard scanning.
    - ``global_source`` / ``global_persistence`` — global scope adapters:
      the source adapter loads and fully validates the declared canonical
      source (bodies + identity) before any write; the persistence
      adapter atomically inserts missing UIDs inside its own transaction
      contract.
    - ``cache`` — completeness cache contract (module docstring); input
      for pack plan B-2.

    Triggers (full import / runtime read / per-public-read) stay with the
    caller; the engine does not read the stored world or decide when to run.
    """

    name: str
    scope: CanonicalScope
    attach_policy: CanonicalAttachPolicy
    identity_field: str = ""
    cache: CanonicalCachePolicy = field(default_factory=CanonicalCachePolicy)
    world_canonical_rows: Callable[[], Iterable[Mapping[str, Any]]] | None = None
    global_source: CanonicalSourceAdapter | None = None
    global_persistence: CanonicalPersistenceAdapter | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise CanonicalSpecError("CanonicalLibrarySpec.name must be non-empty")
        if self.scope is CanonicalScope.WORLD:
            if self.attach_policy is not CanonicalAttachPolicy.WORLD_WIRE_OVERLAY:
                raise CanonicalSpecError(
                    f"{self.name}: scope 'world' requires policy 'world_wire_overlay'",
                )
            if not self.identity_field:
                raise CanonicalSpecError(f"{self.name}: world spec requires identity_field")
            if self.world_canonical_rows is None:
                raise CanonicalSpecError(f"{self.name}: world spec requires world_canonical_rows")
            if self.global_source is not None or self.global_persistence is not None:
                raise CanonicalSpecError(f"{self.name}: world spec forbids global adapters")
        else:
            if self.attach_policy is not CanonicalAttachPolicy.GLOBAL_FILL_MISSING:
                raise CanonicalSpecError(
                    f"{self.name}: scope 'global' requires policy 'global_fill_missing'",
                )
            if self.global_source is None or self.global_persistence is None:
                raise CanonicalSpecError(
                    f"{self.name}: global spec requires global_source and global_persistence",
                )
            if self.world_canonical_rows is not None:
                raise CanonicalSpecError(f"{self.name}: global spec forbids world_canonical_rows")
            if self.identity_field:
                raise CanonicalSpecError(
                    f"{self.name}: global spec forbids identity_field — "
                    "identity lives on CanonicalEntry.uid",
                )
