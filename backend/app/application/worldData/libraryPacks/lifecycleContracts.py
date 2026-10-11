"""Typed lifecycle data; no persistence or domain rules (TZ packs §1–3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.libraryPackMember import LibraryPackMemberRow


@dataclass(frozen=True)
class MemberRef:
    library_kind: str
    template_uid: str
    consumer: str
    path: str

    @property
    def reason(self) -> str:
        return f"{self.consumer}:{self.path}"


@dataclass(frozen=True)
class FieldChange:
    path: tuple[str | int, ...]
    before: Any
    after: Any
    before_present: bool = True
    after_present: bool = True


@dataclass(frozen=True)
class PreparedMember:
    member: LibraryPackMemberRow
    body: dict
    source_file: str | None
    added: bool = False
    changes: tuple[FieldChange, ...] = ()


@dataclass(frozen=True)
class ReinstantiatePreview:
    pack_uid: str
    source_pack_uid: str
    preview_token: str
    prepared: tuple[PreparedMember, ...]
    removed: tuple[str, ...]
    held: dict[str, tuple[str, ...]]
    preserved: tuple[str, ...]
    uid_map: dict[str, str]
    diagnostics: tuple[str, ...] = ()
    created: bool = False
    applied: bool = False
    stale: bool = False
    conflicts: tuple[str, ...] = ()
    metadata_changes: tuple[FieldChange, ...] = ()
    dependencies: tuple[str, ...] = ()

    @property
    def members(self):
        return tuple(p.member for p in self.prepared)


@dataclass(frozen=True)
class MemberCopyResult:
    member: LibraryPackMemberRow
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemberStatus:
    template_uid: str
    status: str
    diagnostics: tuple[str, ...] = ()
