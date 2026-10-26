"""Adapter contracts for the canonical-defaults engine — global scope.

The engine imports no domain models, FS importers, or repositories. A
domain supplies:

- ``CanonicalSourceAdapter.load`` — reads the *declared* canonical source
  (explicit pack/registry list — no wildcard scanning), validates every
  body and the identity of every entry, and returns a fully checked
  ``CanonicalSnapshot``. Loading happens before any write: a source error
  leaves no rows behind.
- ``CanonicalPersistenceAdapter.insert_missing`` — atomically adds the
  missing canonical UIDs inside its own transaction contract. Existing
  rows are never replaced, including user overrides of canonical UIDs
  (``ON CONFLICT(identity) DO NOTHING`` — only the identity conflict is
  ignored; plain ``INSERT OR IGNORE`` is unsafe: it also silently skips
  NOT NULL/CHECK violations). A write
  error rolls the whole attach back; inside a caller transaction the
  adapter participates without a nested BEGIN or a hidden commit of
  foreign work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CanonicalEntry:
    """One canonical member of a global library.

    ``uid`` — canonical identity, minted only via
    ``app.ids`` (DET-1); no uuid/hash/manual
    concatenation in adapters or consumers.
    ``body`` — domain-typed, already validated payload; opaque to the
    engine, consumed by the domain persistence adapter.
    """

    uid: str
    body: Any


@dataclass(frozen=True)
class CanonicalSnapshot:
    """Fully validated canonical source — checked completely before any write.

    ``fingerprint`` — optional version token of the declared source
    (manifest/files). Required when the spec declares
    ``SourceCacheMode.FINGERPRINT``; the engine rejects snapshots without
    it so a cached-source adapter can never silently lose its invalidation
    key.
    """

    entries: tuple[CanonicalEntry, ...] = field(default_factory=tuple)
    fingerprint: str | None = None


@dataclass(frozen=True)
class CanonicalAttachResult:
    """Outcome of one ``ensure_canonical`` call.

    ``added`` — canonical UIDs this call attempted to insert (in declared
    source order). ``existing`` — canonical UIDs already present,
    including user overrides kept untouched. ``added ∪ existing`` must
    equal the declared UID set — enforced by the engine.
    """

    added: tuple[str, ...] = field(default_factory=tuple)
    existing: tuple[str, ...] = field(default_factory=tuple)


class CanonicalSourceAdapter(Protocol):
    """Domain source adapter — load + validate the whole declared source."""

    async def load(self, context: Any) -> CanonicalSnapshot:
        """Return the validated snapshot; raise on any invalid entry.

        ``context`` is the caller-provided handle passed verbatim by
        ``ensure_canonical`` (typically carrying the ``Database``).
        """


class CanonicalPersistenceAdapter(Protocol):
    """Domain persistence adapter — atomic insert-missing."""

    async def insert_missing(
        self,
        snapshot: CanonicalSnapshot,
        context: Any,
    ) -> CanonicalAttachResult:
        """Insert only absent canonical UIDs; never replace existing rows.

        Must own its transaction: commit only work it started itself,
        participate in a caller transaction when already inside one, and
        roll the whole attach back on a write error.
        """
