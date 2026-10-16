"""Result DTOs of the pack application service — TZ §0.2/§2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.models.structureTemplate import StructureTemplateRow


@dataclass(frozen=True)
class PackDeleteResult:
    pack_uid: str
    members_removed: int
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemberDeleteResult:
    template_uid: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackImportResult:
    pack: LibraryPackRow
    bodies: tuple[ReliefTemplateRow | StructureTemplateRow, ...]
    missing_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackRemapResult:
    """Outcome of ``instantiate_pack`` / ``copy_pack`` (TZ §2).

    ``created=False`` marks a re-instantiate returning the existing
    instance identity — member/body rewrite is step 4c's contract.
    """
    pack: LibraryPackRow
    members: tuple[LibraryPackMemberRow, ...]
    uid_map: Mapping[str, str]  # source member uid → remapped member uid
    missing_dependencies: tuple[str, ...] = ()
    created: bool = True
