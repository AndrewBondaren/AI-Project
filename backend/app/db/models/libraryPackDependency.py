"""``library_pack_dependencies`` catalog row — tz_template_library_packs §3.

``required_pack_uid`` deliberately has no FK: a dependency may point to a
not-yet-imported pack; incompleteness is diagnosed, not blocked.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LibraryPackDependencyRow:
    __table__ = "library_pack_dependencies"
    __pk__ = "pack_uid"  # composite PK (pack_uid, required_pack_uid); no BaseRepository pk ops

    pack_uid: str
    required_pack_uid: str
