"""``library_pack_members`` catalog row — tz_template_library_packs §3.

One row fixes the single owner of a member; bodies stay in the domain
SQL tables. ``source_template_uid`` is provenance of the remap
operation, not FK-integrity — dangling is allowed (source member or its
pack may be deleted). The "held by use" / "source deleted" member
statuses are *computed* from provenance resolution, there is no column.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LibraryPackMemberRow:
    __table__ = "library_pack_members"
    __pk__ = "template_uid"

    template_uid: str
    pack_uid: str
    library_kind: str
    local_uid: str
    source_template_uid: str | None = None
