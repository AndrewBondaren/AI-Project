"""Declared default (canonical) library packs — tz_template_library_packs §6.

Explicit trusted declaration per domain; no wildcard scanning of domain
roots ever turns an arbitrary FS pack into a default (decision 2026-10-08).
Default status is an engine declaration by UID (TZ §3): a user manifest can
never assign it to itself. ``_DECLARED_DEFAULT_PACKS`` pairs the source pack
key with its global ``system_name``; filesystem-backed providers use that key
as the folder name. Typed providers and the write gate share this declaration.

- ``structure_templates`` — shipped pack ``base``;
- ``relief_templates`` — **empty**: the domain default is the POJO
  contracts (``canonical_defaults`` policy/registry/scalars, R21); template
  bodies are not shipped as defaults — ``smoke_003`` stays a user pack and
  reaches a world only via explicit instantiate;
- ``plot_templates`` / ``building_templates`` — shipped typed providers,
  backed by the explicitly declared plot fixtures; ordinary canonical members.
"""

from __future__ import annotations

from typing import Mapping

from app.ids import LibraryKind, library_uid

# Global ``system_name`` of the shipped structures default pack — pack
# identity constant (TZ §2), consumed by the migration map as well.
STRUCTURES_BASE_SYSTEM_NAME = "engine.structures.base"
PLOTS_BASE_SYSTEM_NAME = "engine.plots.base"
BUILDINGS_BASE_SYSTEM_NAME = "engine.buildings.base"

# kind → (source pack_name, global system_name)
_DECLARED_DEFAULT_PACKS: Mapping[LibraryKind, tuple[tuple[str, str], ...]] = {
    LibraryKind.STRUCTURE_TEMPLATES: (("base", STRUCTURES_BASE_SYSTEM_NAME),),
    LibraryKind.RELIEF_TEMPLATES: (),
    LibraryKind.PLOT_TEMPLATES: (("base", PLOTS_BASE_SYSTEM_NAME),),
    LibraryKind.BUILDING_TEMPLATES: (("base", BUILDINGS_BASE_SYSTEM_NAME),),
}

# Resolved once at import — the declaration above is a module constant.
_DEFAULT_PACK_UIDS: frozenset[str] = frozenset(
    library_uid(LibraryKind.LIBRARY_PACKS, system_name)
    for pairs in _DECLARED_DEFAULT_PACKS.values()
    for _, system_name in pairs
)


def default_pack_names(kind: LibraryKind) -> tuple[str, ...]:
    """Declared source pack names (folder names for filesystem providers)."""
    return tuple(name for name, _ in _DECLARED_DEFAULT_PACKS.get(LibraryKind(kind), ()))


def default_pack_uids() -> frozenset[str]:
    """UIDs of all declared default packs (the read-only gate key, TZ §3)."""
    return _DEFAULT_PACK_UIDS


def is_default_pack_uid(pack_uid: str) -> bool:
    """True when *pack_uid* is a declared default pack — read-only for writes."""
    return pack_uid in _DEFAULT_PACK_UIDS
