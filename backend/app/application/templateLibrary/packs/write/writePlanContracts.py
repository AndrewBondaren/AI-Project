"""Typed write actions and previews, without callbacks/SQL (packs TZ §0.3)."""
from dataclasses import dataclass

from app.application.jsonValidation.types import FieldPathError
from app.application.templateLibrary.packs.lifecycleContracts import FieldChange
from app.application.templateLibrary.packs.write.writeContracts import WriteItemDecision
from app.application.templateLibrary.packs.write.writeInspectionContracts import InspectedMember, InspectedSource
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World


@dataclass(frozen=True)
class MemberWrite:
    value: InspectedMember
    added: bool
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class PackWrite:
    value: LibraryPackRow
    added: bool
    dependencies: tuple[str, ...]
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class WriteProjection:
    """Identity allocation, before any bodies or retention are projected."""
    decision: WriteItemDecision
    owner_world_uid: str | None
    source: InspectedSource
    pack: LibraryPackRow
    pack_added: bool
    members: tuple[tuple[InspectedMember, LibraryPackMemberRow], ...]
    uid_map: tuple[tuple[str, str], ...]
    candidates: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()


@dataclass(frozen=True)
class WriteItemPlan:
    item_key: str
    pack: PackWrite | None
    members: tuple[MemberWrite, ...]
    uid_map: tuple[tuple[str, str], ...]
    candidates: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldWrite:
    before: World
    after: World
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class LibraryWritePlan:
    preview_token: str
    items: tuple[WriteItemPlan, ...]
    removed: tuple[LibraryPackMemberRow, ...]
    held: tuple[tuple[str, tuple[str, ...]], ...]
    worlds: tuple[WorldWrite, ...]
    diagnostics: tuple[FieldPathError, ...]
