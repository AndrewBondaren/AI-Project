"""Typed lifecycle data; no persistence or domain rules (TZ packs §1–3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from app.application.jsonValidation.types import FieldPathError

from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.world import World


@dataclass(frozen=True)
class CatalogSnapshot:
    members: dict[str, LibraryPackMemberRow]
    bodies: dict[str, dict]
    source_files: dict[str, str | None]


@dataclass(frozen=True)
class ReinstantiateSnapshot:
    source: LibraryPackRow
    instance: LibraryPackRow
    world: World
    catalog: CatalogSnapshot
    source_members: tuple[LibraryPackMemberRow, ...]
    source_bodies: dict[str, dict]
    source_files: dict[str, str | None]
    known_members: dict[str, LibraryPackMemberRow]
    source_dependencies: tuple[str, ...]
    target_dependencies: tuple[str, ...]
    existing_dependencies: frozenset[str]


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
class MemberProjection:
    current: dict[str, LibraryPackMemberRow]
    prepared: tuple[PreparedMember, ...]
    uid_map: dict[str, str]
    candidates: frozenset[str]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class RetentionPlan:
    members: dict[str, LibraryPackMemberRow]
    refs: tuple[MemberRef, ...]
    held: dict[str, tuple[str, ...]]
    removed: tuple[str, ...]
    preserved: tuple[str, ...]
    dependencies: tuple[str, ...]
    existing_dependencies: tuple[str, ...]


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
    resolve_issues: tuple[FieldPathError, ...] = ()

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
