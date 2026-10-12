"""Application write outcomes; transport serialization belongs to L-5."""
from dataclasses import dataclass

from app.application.worldData.libraryPacks.writeContracts import WriteChoice, WriteItemDecision
from app.application.worldData.libraryPacks.writePlanContracts import LibraryWritePlan


@dataclass(frozen=True)
class CopyPreview:
    source_member_uids: tuple[str, ...]
    owner_world_uid: str | None
    target_pack_uid: str | None
    remaps_internal_references: bool
    requires_pack_system_name: bool
    # New identities are allocated only for apply; existing records are preserved.
    source_unchanged: bool = True
    replaces_existing: bool = False


@dataclass(frozen=True)
class WritePreview:
    """Conditional projection of its listed actions, never an authorization."""
    actions: tuple[WriteItemDecision, ...]
    plan: LibraryWritePlan | None = None
    issues: tuple[str, ...] = ()
    copy: CopyPreview | None = None


@dataclass(frozen=True)
class WriteResult:
    plan: LibraryWritePlan
    status: str = "applied"


@dataclass(frozen=True)
class PolicyRequired:
    preview_token: str
    choices: tuple[WriteChoice, ...]
    preview: tuple[WritePreview, ...]
    stale: bool = False
    status: str = "policy_required"


@dataclass(frozen=True)
class WriteRejected:
    issues: tuple[str, ...]
    choices: tuple[WriteChoice, ...] = ()
    status: str = "rejected"


LibraryWriteOutcome = WriteResult | PolicyRequired | WriteRejected
