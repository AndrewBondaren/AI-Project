"""Declared default (canonical) library packs — tz_template_library_packs §6.

Explicit trusted declaration per domain; no wildcard scanning of domain
roots ever turns an arbitrary FS pack into a default (decision 2026-10-08).

- ``structure_templates`` — shipped pack ``base``;
- ``relief_templates`` — **empty**: the domain default is the POJO
  contracts (``canonical_defaults`` policy/registry/scalars, R21); template
  bodies are not shipped as defaults — ``smoke_003`` stays a user pack and
  reaches a world only via explicit instantiate;
- ``building_templates`` — **empty**: builtin parent plots live in the POJO
  default layer (``canonical_defaults()`` over ``fixtures/templates/``);
  importing them as pack members would create a second source of truth
  over the POJO (clarification 2026-10-09).
"""

from __future__ import annotations

from typing import Mapping

from app.ids import LibraryKind

DEFAULT_LIBRARY_PACKS: Mapping[LibraryKind, tuple[str, ...]] = {
    LibraryKind.STRUCTURE_TEMPLATES: ("base",),
    LibraryKind.RELIEF_TEMPLATES: (),
    LibraryKind.BUILDING_TEMPLATES: (),
}


def default_pack_names(kind: LibraryKind) -> tuple[str, ...]:
    """Declared default pack names (folder names under the domain root)."""
    return DEFAULT_LIBRARY_PACKS.get(LibraryKind(kind), ())
