"""Read-side inputs and retained state for write planning (packs TZ §0.3)."""
from dataclasses import dataclass

from app.application.templateLibrary.packs.domainAdapters.contract import DomainOutline
from app.application.templateLibrary.packs.lifecycleContracts import MemberRef
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World


@dataclass(frozen=True)
class WriteImportMember:
    member: LibraryPackMemberRow
    body: dict
    source_file: str | None = None


@dataclass(frozen=True)
class WriteImportSource:
    """Parsed FS/archive input, keyed by import entry, never by a client path.

    The transport reader owns parsing the container. The inspector validates
    these bodies through domain adapters before returning an executable snapshot.
    """
    pack: LibraryPackRow
    members: tuple[WriteImportMember, ...]
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class InspectedMember:
    member: LibraryPackMemberRow
    body: dict
    outline: DomainOutline
    source_file: str | None = None


@dataclass(frozen=True)
class InspectedSource:
    pack: LibraryPackRow
    members: tuple[InspectedMember, ...]
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class WriteScopeState:
    owner_world_uid: str | None
    world: World | None
    packs: tuple[LibraryPackRow, ...]
    members: tuple[InspectedMember, ...]
    dependencies: tuple[tuple[str, tuple[str, ...]], ...]
    refs: tuple[MemberRef, ...]
    pins: tuple[tuple[str, tuple[str, ...]], ...]
    # Persisted NamedLocation template refs (B4) — projection-invariant
    # consumers the retention planner merges with the projected catalog refs.
    location_refs: tuple[MemberRef, ...] = ()


@dataclass(frozen=True)
class WriteInspectionState:
    sources: tuple[tuple[str, InspectedSource], ...]
    scopes: tuple[WriteScopeState, ...]
    # Ownership of external dependencies/ref targets is diagnostic only.
    known_packs: tuple[LibraryPackRow, ...]
    known_members: tuple[LibraryPackMemberRow, ...]
    dependency_edges: tuple[tuple[str, tuple[str, ...]], ...]
    existing_member_uids: tuple[str, ...] = ()
