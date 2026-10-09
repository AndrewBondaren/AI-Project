"""Canonical-defaults engine — domain-agnostic canonical attach.

Plan: ``.cursor/plans/canonical-defaults-engine.md`` (step 2).
SoT: ``docs/tz_json_validation.md`` § «Единый движок canonical defaults»,
``docs/tz_template_library_packs.md`` §6.

Domains register only via ``CanonicalLibrarySpec`` + adapters; the engine
imports no domain models, FS importers, or repositories.

- ``canonical_merge`` — world scope: wire-overlay before validation.
- ``ensure_canonical`` — global scope: validated source → atomic
  insert-missing. Completeness = all canonical UIDs present; the cache
  contract is declared by ``CanonicalCachePolicy`` (see ``spec.py`` —
  input for pack plan B-2).
"""

from app.application.canonicalLibrary.adapters import (
    CanonicalAttachResult,
    CanonicalEntry,
    CanonicalPersistenceAdapter,
    CanonicalSnapshot,
    CanonicalSourceAdapter,
)
from app.application.canonicalLibrary.engine import (
    canonical_merge,
    ensure_canonical,
)
from app.application.canonicalLibrary.spec import (
    CanonicalAttachPolicy,
    CanonicalCachePolicy,
    CanonicalContractError,
    CanonicalLibraryError,
    CanonicalLibrarySpec,
    CanonicalScope,
    CanonicalSourceError,
    CanonicalSpecError,
    FullnessCacheMode,
    SourceCacheMode,
)
from app.application.canonicalLibrary.sqlPersistence import SqlCanonicalPersistence

__all__ = [
    "CanonicalAttachPolicy",
    "CanonicalAttachResult",
    "CanonicalCachePolicy",
    "CanonicalContractError",
    "CanonicalEntry",
    "CanonicalLibraryError",
    "CanonicalLibrarySpec",
    "CanonicalPersistenceAdapter",
    "CanonicalScope",
    "CanonicalSnapshot",
    "CanonicalSourceAdapter",
    "CanonicalSourceError",
    "CanonicalSpecError",
    "FullnessCacheMode",
    "SourceCacheMode",
    "SqlCanonicalPersistence",
    "canonical_merge",
    "ensure_canonical",
]
