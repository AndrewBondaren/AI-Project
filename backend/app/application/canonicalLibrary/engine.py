"""Domain-agnostic canonical-defaults engine.

Two operations over domain-declared ``CanonicalLibrarySpec``:

- ``canonical_merge(spec, raw)`` — world wire-overlay (invariant 2 of the
  plan): pure merge of raw wire fields *before* validation. World/explicit
  rows come first so validation error indices are preserved; on a matching
  ``identity_field`` key explicit fields win and missing fields inherit
  the canonical row; canonical-only keys are appended; explicit
  ``false``/``0``/``[]``/``null`` are values, not absence. Semantic
  validation stays with the resolver — invalid shapes pass through
  unchanged.
- ``ensure_canonical(spec, context)`` — global fill-missing: the source
  adapter loads and validates the *entire* declared canonical source
  (including identity uniqueness — also enforced here contract-side),
  then the persistence adapter atomically inserts missing UIDs. Errors
  leave no rows; a failed attach marks nothing and may be retried.

Concurrent attaches serialize on a per-``spec.name`` in-process lock;
cross-process safety comes from the atomic SQL conflict (``INSERT OR
IGNORE`` never replaces a row). Completeness is defined by presence of
all canonical UIDs — see ``CanonicalCachePolicy`` in ``spec.py`` for the
fixed cache contract.

UIDs are minted only via ``app.application.worldData.ids`` (DET-1);
logging goes through ``app.core.loggingConfig`` (this logger routes to
the ``core/runtime`` sink).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.canonicalLibrary.adapters import (
    CanonicalAttachResult,
    CanonicalSnapshot,
)
from app.application.canonicalLibrary.spec import (
    CanonicalAttachPolicy,
    CanonicalContractError,
    CanonicalLibrarySpec,
    CanonicalScope,
    CanonicalSpecError,
    CanonicalSourceError,
    SourceCacheMode,
)

log = logging.getLogger(__name__)

# Per-domain in-process serializer for attach (TZ §6: concurrent attaches
# are serialized at the library/DB level). Plain dict — specs are few and
# permanent.
_attach_locks: dict[str, asyncio.Lock] = {}


def canonical_merge(spec: CanonicalLibrarySpec, raw: Any) -> Any:
    """World wire-overlay merge — pure, before validation (plan invariant 2)."""
    if (
        spec.scope is not CanonicalScope.WORLD
        or spec.attach_policy is not CanonicalAttachPolicy.WORLD_WIRE_OVERLAY
    ):
        raise CanonicalSpecError(
            f"{spec.name}: canonical_merge requires scope 'world' "
            "with policy 'world_wire_overlay'",
        )
    if raw is not None and not isinstance(raw, list):
        return raw
    rows_provider = spec.world_canonical_rows
    assert rows_provider is not None  # spec.__post_init__ guarantees it
    canonical = {row[spec.identity_field]: dict(row) for row in rows_provider()}
    merged: list[Any] = []
    present: set[Any] = set()
    for row in raw or []:
        key = row.get(spec.identity_field) if isinstance(row, dict) else None
        if isinstance(key, str):
            merged.append({**canonical.get(key, {}), **row})
            present.add(key)
        else:
            merged.append(row)
    merged.extend(row for key, row in canonical.items() if key not in present)
    return merged


async def ensure_canonical(
    spec: CanonicalLibrarySpec,
    context: Any,
) -> CanonicalAttachResult:
    """Global fill-missing attach — validated source, then atomic insert-missing.

    ``context`` is passed verbatim to the spec's adapters (typically the
    ``app.db.database.Database``). Result: added/existing canonical UIDs.
    """
    if (
        spec.scope is not CanonicalScope.GLOBAL
        or spec.attach_policy is not CanonicalAttachPolicy.GLOBAL_FILL_MISSING
    ):
        raise CanonicalSpecError(
            f"{spec.name}: ensure_canonical requires scope 'global' "
            "with policy 'global_fill_missing'",
        )
    assert spec.global_source is not None
    assert spec.global_persistence is not None
    async with _attach_locks.setdefault(spec.name, asyncio.Lock()):
        snapshot = await spec.global_source.load(context)
        _check_snapshot(spec, snapshot)
        result = await spec.global_persistence.insert_missing(snapshot, context)
        _check_result(spec, snapshot, result)
    if result.added:
        log.info(
            "canonical attach %s: added=%d existing=%d",
            spec.name,
            len(result.added),
            len(result.existing),
        )
    else:
        log.debug(
            "canonical attach %s: complete (existing=%d)",
            spec.name,
            len(result.existing),
        )
    return result


def _check_snapshot(spec: CanonicalLibrarySpec, snapshot: CanonicalSnapshot) -> None:
    uids = [entry.uid for entry in snapshot.entries]
    if any(not isinstance(uid, str) or not uid for uid in uids):
        raise CanonicalSourceError(f"{spec.name}: canonical uid must be a non-empty str")
    if len(set(uids)) != len(uids):
        raise CanonicalSourceError(f"{spec.name}: duplicate canonical uid in source")
    if spec.cache.source is SourceCacheMode.FINGERPRINT and not snapshot.fingerprint:
        raise CanonicalSourceError(
            f"{spec.name}: source cache mode 'fingerprint' requires "
            "CanonicalSnapshot.fingerprint",
        )


def _check_result(
    spec: CanonicalLibrarySpec,
    snapshot: CanonicalSnapshot,
    result: CanonicalAttachResult,
) -> None:
    declared = {entry.uid for entry in snapshot.entries}
    added = set(result.added)
    existing = set(result.existing)
    if added & existing or added | existing != declared:
        raise CanonicalContractError(
            f"{spec.name}: persistence result must partition the declared "
            "canonical uid set into added ∪ existing",
        )
