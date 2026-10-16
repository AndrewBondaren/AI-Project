"""Pure B1 facts and projected migration output; B2 alone owns execution."""
from dataclasses import dataclass
from enum import StrEnum

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.worldData.libraryPacks.legacyDomainContracts import LegacyDomainShape, SourcePath
from app.application.worldData.libraryPacks.legacyWorldInput import LegacyWorldInput
from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot, FieldChange
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportSource, WriteImportMember
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.db.models.libraryPack import LibraryPackRow


class LegacyPackRoute(StrEnum):
    INSTANCE = "instance"
    REUSE = "reuse"
    LEGACY = "legacy"


@dataclass(frozen=True)
class LegacyWorldFacts:
    """Caller supplies complete pack/member/body snapshots, including existing instances."""
    packs: tuple[WriteImportSource, ...] = ()
    uid_aliases: tuple[tuple[str, str], ...] = ()
    body_shapes: tuple[tuple[str, LegacyDomainShape], ...] = ()


@dataclass(frozen=True)
class LegacyPointerDecision:
    path: SourcePath
    source_uid: str
    target_uid: str | None
    library_kind: str | None
    route: str


@dataclass(frozen=True)
class LegacyBodyComparison:
    path: SourcePath
    source_uid: str
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class LegacyPackProjection:
    source_pack_uid: str | None
    target_pack: LibraryPackRow
    route: LegacyPackRoute
    members: tuple[WriteImportMember, ...]
    dependencies: tuple[str, ...]
    # All source records are kept; common writer receives these in B2.
    source: WriteImportSource | None = None
    source_pack_uids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegacyWorldMigrationPlan:
    original: LegacyWorldInput
    facts: LegacyWorldFacts
    projected_world: dict
    pins: tuple[LibraryPinEntry, ...]
    packs: tuple[LegacyPackProjection, ...]
    pointers: tuple[LegacyPointerDecision, ...]
    comparisons: tuple[LegacyBodyComparison, ...]
    uid_map: tuple[tuple[str, str], ...]
    catalog: CatalogSnapshot
    diagnostics: tuple[FieldPathError, ...]
    issues: tuple[FieldPathError, ...]

    @property
    def valid(self):
        return not self.issues

    def require_valid(self):
        if self.issues:
            raise ImportValidationError(list(self.issues))
        return self
