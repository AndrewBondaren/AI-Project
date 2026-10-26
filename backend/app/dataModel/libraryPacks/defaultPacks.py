"""Declared default library-pack identities — tz_template_library_packs §3/§6.

The system names are pack *identity constants* shared by the application
defaults declaration and domain code that must address canonical members
(e.g. canonical district recipe pins). Member identity derives through the
central ``library_uid`` contract — names are pack keys, never a runtime
lookup against the catalog.
"""

from __future__ import annotations

from app.ids import LibraryKind, library_uid

STRUCTURES_BASE_SYSTEM_NAME = "engine.structures.base"
PLOTS_BASE_SYSTEM_NAME = "engine.plots.base"
BUILDINGS_BASE_SYSTEM_NAME = "engine.buildings.base"

_BASE_PACK_OF: dict[LibraryKind, str] = {
    LibraryKind.PLOT_TEMPLATES: PLOTS_BASE_SYSTEM_NAME,
    LibraryKind.BUILDING_TEMPLATES: BUILDINGS_BASE_SYSTEM_NAME,
    LibraryKind.STRUCTURE_TEMPLATES: STRUCTURES_BASE_SYSTEM_NAME,
}


def default_pack_uid(system_name: str) -> str:
    """Uid of a declared default pack (engine declaration by UID, TZ §3)."""
    return library_uid(LibraryKind.LIBRARY_PACKS, system_name)


def canonical_member_uid(kind: LibraryKind, local_uid: str) -> str:
    """Member uid of a canonical record inside its declared base pack.

    Deterministic — same formula the canonical attach writes to SQL, so a
    canonical recipe key may name the member without touching the catalog.
    """
    base = _BASE_PACK_OF.get(LibraryKind(kind))
    if base is None:
        raise ValueError(f"no canonical base pack declared for {kind}")
    return library_uid(LibraryKind(kind), local_uid, pack_uid=default_pack_uid(base))
