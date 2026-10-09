"""World-owned ``legacy`` pack — destination of manifest-less bundle bodies.

Bodies arriving through a flat legacy body section (no manifest) become
members of the ``legacy`` pack owned by the importing world — the world's
authored records (TZ §1.1), not a synthetic engine pack (plan step 3).
Identity is fully derived from ``world_uid`` through the central
``library_uid`` formula, so re-import is stable without runtime guessing.
"""

from __future__ import annotations

from app.ids import LibraryKind, library_uid
from app.application.worldData.libraryPacks.uidMap import former_template_uid
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository

LEGACY_PACK_NAME = "legacy"


def legacy_pack_system_name(world_uid: str) -> str:
    return f"world.{world_uid}.legacy"


def legacy_pack_uid(world_uid: str) -> str:
    return library_uid(LibraryKind.LIBRARY_PACKS, legacy_pack_system_name(world_uid))


def legacy_member_uid(kind: LibraryKind, local_uid: str, *, world_uid: str) -> str:
    return library_uid(
        LibraryKind(kind), local_uid, pack_uid=legacy_pack_uid(world_uid)
    )


def legacy_pack_row(world_uid: str) -> LibraryPackRow:
    return LibraryPackRow(
        pack_uid=legacy_pack_uid(world_uid),
        system_name=legacy_pack_system_name(world_uid),
        pack_name=LEGACY_PACK_NAME,
        display_name="Legacy",
        owner_world_uid=world_uid,
    )


def legacy_member_row(
    kind: LibraryKind, local_uid: str, *, world_uid: str
) -> LibraryPackMemberRow:
    """Member row for a manifest-less body; ``source_template_uid`` keeps the
    former uid when the migration map knows it (TZ §4 legacy, plan 5b)."""
    return LibraryPackMemberRow(
        template_uid=legacy_member_uid(kind, local_uid, world_uid=world_uid),
        pack_uid=legacy_pack_uid(world_uid),
        library_kind=LibraryKind(kind).value,
        local_uid=local_uid,
        source_template_uid=former_template_uid(kind, local_uid),
    )


async def ensure_legacy_pack(
    world_uid: str, packs: ILibraryPackRepository
) -> LibraryPackRow:
    """Idempotent insert of the world-owned legacy pack; returns its row."""
    row = legacy_pack_row(world_uid)
    await packs.insert_missing([row])
    return row
