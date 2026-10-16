"""Pure legacy split inputs/results; caller declares shape, owner and identity."""
from dataclasses import dataclass
from enum import StrEnum

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.templateLibrary.packs.domainAdapters.contract import DomainOutline
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind

type SourcePath = tuple[str | int, ...]
LEGACY_PLOT_FIELDS = ("plot_type", "main_building", "secondary_buildings", "occupied_footprint")


class LegacyDomainShape(StrEnum):
    MODERN = "modern"
    PLOT = "legacy_plot"
    BUILDING_OUTLINE = "legacy_building_outline"


@dataclass(frozen=True)
class LegacyDomainRecord:
    """Destination member is declared, never chosen by name/body heuristics."""
    member: LibraryPackMemberRow
    source_kind: LibraryKind
    shape: LegacyDomainShape
    body: dict
    path: SourcePath
    source_uid: str | None = None
    source_file: str | None = None


@dataclass(frozen=True)
class LegacyDomainProvenance:
    source_uid: str | None
    target_uid: str
    source_kind: LibraryKind
    target_kind: LibraryKind
    path: SourcePath


@dataclass(frozen=True)
class EmbeddedBodyPath:
    """Inline body identity belongs to its plot; template_uid is not invented."""
    path: SourcePath
    owner_template_uid: str
    library_kind: LibraryKind = LibraryKind.BUILDING_TEMPLATES


@dataclass(frozen=True)
class LegacyReferenceResolution:
    path: SourcePath
    library_kind: LibraryKind
    source_value: str
    target_uid: str


@dataclass(frozen=True)
class ConvertedDomainRecord:
    member: LibraryPackMemberRow
    body: dict
    prepared: DomainOutline
    provenance: LegacyDomainProvenance
    embedded: tuple[EmbeddedBodyPath, ...]
    references: tuple[LegacyReferenceResolution, ...]
    source_file: str | None


@dataclass(frozen=True)
class LegacyDomainSplitResult:
    sources: tuple[LegacyDomainRecord, ...]
    converted: tuple[ConvertedDomainRecord, ...]
    uid_map: tuple[tuple[str, str], ...]
    issues: tuple[FieldPathError, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    def require_valid(self) -> tuple[ConvertedDomainRecord, ...]:
        if self.issues:
            raise ImportValidationError(list(self.issues))
        return self.converted
