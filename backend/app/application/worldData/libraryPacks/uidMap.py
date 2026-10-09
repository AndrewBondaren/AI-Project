"""Explicit old→new UID map — plan library-packs-model.md step 3.

File-level, one-shot migration artifact (TZ §4 «Legacy fixtures/bundle»);
no runtime owner guessing and no dual UID support for migrated content.

The map covers the three reference classes:

1. **Pointer entries** of world registries — old ``system_template_uid``
   pointers become ``LibraryPinEntry`` pairs ``(library_kind, local_uid)``;
   the pin's ``local_uid`` is the member's local key in the pack that now
   owns the body (equal to the body ``system_name`` for name-keyed
   domains).
2. **Manifest-less bundle bodies** — a flat body section becomes members
   of the world-owned ``legacy`` pack of the importing world; the member
   uid is ``legacy_member_uid(kind, local_uid, world_uid=…)`` and
   ``source_template_uid`` stores the former uid when this map knows it
   (``former_template_uid``).
3. **Refs inside bodies / world-side refs** — plot
   ``main_building.structure`` and pick-policy ``default_template_uid``
   rewrite by the same table: shipped FS content → its engine pack member
   uid; bundle-shipped world content → the world's ``legacy`` member uid.

Former identity literals: the pre-B-1 relief ids were minted by the retired
NAMESPACE_URL scheme over ``"relief_templates|{name}"``, so they are
recorded as literals; structure ids were author-picked UUIDs — also
literals. New identities are always computed through the central
``library_uid`` (DET-1) — never by local formulas.
"""

from __future__ import annotations

from typing import Mapping

from app.ids import LibraryKind, library_uid
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry

# Globally stable pack keys (TZ §2): system_name is the author's global key;
# pack_name is only the FS folder name.
STRUCTURES_BASE_SYSTEM_NAME = "engine.structures.base"
SMOKE_003_SYSTEM_NAME = "user.relief.smoke_003"

# Old authored structure UUID (former ``system_name``/file stem) → member
# local_uid inside pack ``base``. Semantic keys follow each template's role.
STRUCTURE_MEMBER_RENAMES: Mapping[str, str] = {
    "0f6d7a8b-9c0d-4e1f-9a2b-4c5d6e7f8a9b": "mill",
    "1a7e8b9c-0d1e-4f2a-8b3c-5d6e7f8a9b0c": "smelter",
    "2b8f9c0d-1e2f-4a3b-9c4d-6e7f8a9b0c1d": "workshop",
    "3c9a0d1e-2f3a-4b4c-8d5e-7f8a9b0c1d2e": "temple",
    "4d0b1e2f-3a4b-4c5d-9e6f-8a9b0c1d2e3f": "theater",
    "5a1f2b3c-4d5e-4f6a-8b7c-9d0e1f2a3b4c": "tavern_1",
    "5e1c2f3a-4b5c-4d6e-8f7a-9b0c1d2e3f4a": "library",
    "6b2f3c4d-5e6f-4a7b-9c8d-0e1f2a3b4c5d": "tavern_2",
    "6f2d3a4b-5c6d-4e7f-9a8b-0c1d2e3f4a5b": "farm",
    "7a3e4b5c-6d7e-4f8a-8b9c-1d2e3f4a5b6c": "livestock",
    "7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e": "manor_1",
    "8d4b5e6f-7a8b-4c9d-9e0f-2a3b4c5d6e7f": "town_hall",
    "9e5c6f7a-8b9c-4d0e-8f1a-3b4c5d6e7f8a": "mine",
}

# Retired NAMESPACE_URL scheme uid over ``"relief_templates|{name}"`` → member
# local_uid inside user pack ``smoke_003``.
RELIEF_SMOKE_003_FORMER_UIDS: Mapping[str, str] = {
    "21fb5cb8-eb9a-5f5d-a75b-e632135fc0b5": "open_land_soft",
    "f80e22de-09b1-5f0b-b773-5bd58cab6f10": "shore_soft",
    "1296ee22-f830-5a85-9a55-1f1b46afd3a3": "road_shoulder_soft",
    "67fdb229-267e-5996-bfb9-0ef15f18061c": "ravine_soft",
}

_FORMER_UID_TABLES: Mapping[LibraryKind, Mapping[str, str]] = {
    LibraryKind.STRUCTURE_TEMPLATES: STRUCTURE_MEMBER_RENAMES,
    LibraryKind.RELIEF_TEMPLATES: RELIEF_SMOKE_003_FORMER_UIDS,
}


def pack_uid_for(system_name: str) -> str:
    """Pack uid by the central formula (``library_uid(LIBRARY_PACKS, …)``)."""
    return library_uid(LibraryKind.LIBRARY_PACKS, system_name)


def structures_base_pack_uid() -> str:
    return pack_uid_for(STRUCTURES_BASE_SYSTEM_NAME)


def smoke_003_pack_uid() -> str:
    return pack_uid_for(SMOKE_003_SYSTEM_NAME)


def base_member_uid(local_uid: str) -> str:
    return library_uid(
        LibraryKind.STRUCTURE_TEMPLATES, local_uid,
        pack_uid=structures_base_pack_uid(),
    )


def smoke_003_member_uid(local_uid: str) -> str:
    return library_uid(
        LibraryKind.RELIEF_TEMPLATES, local_uid,
        pack_uid=smoke_003_pack_uid(),
    )


def mapped_template_uid(old_uid: str) -> str | None:
    """Canonical new engine uid of shipped content, or None when unmapped.

    World-bundle bodies covered by a legacy world pack resolve to that
    world's member uid instead (``legacy_member_uid``) — callers pick the
    scope; this helper answers the engine-level identity.
    """
    if old_uid in STRUCTURE_MEMBER_RENAMES:
        return base_member_uid(STRUCTURE_MEMBER_RENAMES[old_uid])
    if old_uid in RELIEF_SMOKE_003_FORMER_UIDS:
        return smoke_003_member_uid(RELIEF_SMOKE_003_FORMER_UIDS[old_uid])
    return None


def former_template_uid(kind: LibraryKind, local_uid: str) -> str | None:
    """The pre-migration uid of a shipped member (``source_template_uid``
    provenance), or None when the map has no former identity for it."""
    table = _FORMER_UID_TABLES.get(LibraryKind(kind), {})
    for old_uid, local in table.items():
        if local == local_uid:
            return old_uid
    return None


def pin_for_member(kind: LibraryKind, local_uid: str) -> dict:
    """Pin entry form for a migrated pointer — ``worlds.library_pins[]``."""
    return LibraryPinEntry(
        library_kind=LibraryKind(kind).value,
        local_uid=local_uid,
    ).model_dump(mode="json")
