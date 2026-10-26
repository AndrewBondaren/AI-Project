"""``library_packs`` catalog row — tz_template_library_packs §3.

Exactly one owner: ``owner_world_uid`` NULL = engine library, non-null =
world library (mutable, dies with the world). ``source_pack_uid`` is
provenance of the remap operation, not FK-integrity — a deleted source
pack leaves a dangling value read as the "source deleted" status.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LibraryPackRow:
    __table__ = "library_packs"
    __pk__ = "pack_uid"
    # Identity + provenance are immutable: save() degrades to the
    # metadata-only update (update_metadata is the declared path).
    __update_exclude__ = frozenset({
        "system_name", "owner_world_uid", "source_pack_uid",
    })

    pack_uid: str
    system_name: str
    pack_name: str
    display_name: str
    version: str = "1.0"
    owner_world_uid: str | None = None
    source_pack_uid: str | None = None
