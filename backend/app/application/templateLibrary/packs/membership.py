"""Effective membership pack set — the one selection shared by the write-path
usage index (``referenceResolver``) and the runtime read facade
(``effectiveCatalog``), TZ packs §1/§1.1.

Availability = ownership or declared default: a world sees its own packs
plus the declared defaults; the engine scope sees engine user packs plus
defaults. No ``list_all`` bypass — a pack outside this set is never a
candidate, whatever its presence in SQL.
"""

from __future__ import annotations

from app.application.templateLibrary.packs.defaults import default_pack_uids
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository


async def membership_pack_uids(
    packs: ILibraryPackRepository, world_uid: str | None
) -> list[str]:
    """Sorted pack uids of the effective membership for *world_uid*
    (``None`` = engine scope): owned packs ∪ declared defaults."""
    owned = (
        await packs.list_world_owned(world_uid)
        if world_uid is not None
        else await packs.list_engine()
    )
    return sorted({p.pack_uid for p in owned} | set(default_pack_uids()))
