"""Write negotiation DTOs; no I/O or identity generation (packs TZ §0.3)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ids import LibraryKind, UID_PART_SEPARATOR

if TYPE_CHECKING:
    from app.application.worldData.libraryPacks.writeInspectionContracts import WriteInspectionState


class WriteObjectKind(StrEnum):
    PACK = "pack"
    MEMBER = "member"


class WritePolicy(StrEnum):
    COPY = "copy"
    REPLACE = "replace"


class WriteAction(StrEnum):
    CREATE = "create"
    COPY = "copy"
    REPLACE = "replace"


class WriteStatus(StrEnum):
    READY = "ready"
    POLICY_REQUIRED = "policy_required"
    REJECTED = "rejected"


class WriteSourceKind(StrEnum):
    CATALOG = "catalog"
    IMPORT = "import"
    AUTHORING = "authoring"


class WriteSource(BaseModel):
    """Catalog UID or import entry key; resolved by the inspector, never a path."""
    model_config = ConfigDict(frozen=True)
    kind: WriteSourceKind
    key: str = Field(min_length=1)


class LibraryWriteItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    item_key: str = Field(min_length=1)
    object_kind: WriteObjectKind
    source: WriteSource
    owner_world_uid: str | None = None
    target_pack_uid: str | None = None
    library_kind: LibraryKind | None = None
    # Application-selected identity for owner attach; not a copy/replace decision.
    target_system_name: str | None = None

    @model_validator(mode="after")
    def validate_destination(self):
        if self.target_system_name is not None and (
            self.object_kind is not WriteObjectKind.PACK or self.source.kind is not WriteSourceKind.IMPORT
            or not self.target_system_name.strip() or UID_PART_SEPARATOR in self.target_system_name
            or self.target_system_name != self.target_system_name.strip()
        ):
            raise ValueError("target_system_name requires a normalized imported pack identity")
        if self.object_kind is WriteObjectKind.MEMBER:
            if not self.target_pack_uid or self.library_kind in (None, LibraryKind.LIBRARY_PACKS):
                raise ValueError("member requires target_pack_uid and a member library_kind")
        elif self.target_pack_uid is not None or self.library_kind is not None:
            raise ValueError("pack destination is an owner scope, not a member destination")
        if self.owner_world_uid is not None and not self.owner_world_uid.strip():
            raise ValueError("owner_world_uid must be nonempty or null for engine scope")
        return self


class LibraryWriteSelection(BaseModel):
    model_config = ConfigDict(frozen=True)
    item_key: str = Field(min_length=1)
    policy: WritePolicy
    target_uid: str | None = None
    copy_system_name: str | None = None

    @model_validator(mode="after")
    def validate_selection(self):
        if self.policy is WritePolicy.REPLACE:
            if not self.target_uid or self.copy_system_name is not None:
                raise ValueError("replace requires target_uid and forbids copy_system_name")
        elif self.target_uid is not None:
            raise ValueError("copy must not select an existing target_uid")
        if self.copy_system_name is not None:
            if not self.copy_system_name.strip() or UID_PART_SEPARATOR in self.copy_system_name:
                raise ValueError(
                    f"copy_system_name must be a nonempty identity key "
                    f"without {UID_PART_SEPARATOR!r}"
                )
            if self.copy_system_name != self.copy_system_name.strip():
                raise ValueError("copy_system_name must be normalized")
        return self


class LibraryWriteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[LibraryWriteItem, ...] = Field(min_length=1)
    decisions: tuple[LibraryWriteSelection, ...] = ()
    preview_token: str | None = None

    @model_validator(mode="after")
    def validate_keys(self):
        keys = [item.item_key for item in self.items]
        selected = [decision.item_key for decision in self.decisions]
        if len(set(keys)) != len(keys) or len(set(selected)) != len(selected):
            raise ValueError("item and decision keys must be unique")
        if not set(selected) <= set(keys):
            raise ValueError("decision names an unknown item")
        return self


def validated_write_request(**kwargs) -> LibraryWriteRequest:
    """Turn invalid external selections into a domain validation failure."""
    from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
    try:
        return LibraryWriteRequest(**kwargs)
    except ValueError as exc:
        raise LibraryPackValidationError(str(exc)) from exc


@dataclass(frozen=True)
class WriteTarget:
    uid: str
    owner_world_uid: str | None
    is_default: bool = False
    writable: bool = True


@dataclass(frozen=True)
class WriteItemSnapshot:
    """Inspector facts. Domain/access errors block both policies.

    Destination is the target pack for members, an authorized owner-scope
    descriptor for packs. Existing pack collisions belong in matches, so
    a read-only match does not prohibit a copy into a writable scope.
    """
    item: LibraryWriteItem
    destination: WriteTarget
    matches: tuple[WriteTarget, ...] = ()
    issues: tuple[str, ...] = ()
    source_owner_world_uid: str | None = None
    # Bound to the requested new pack key; occupied keys are never overwritten.
    copy_system_name: str | None = None
    copy_identity_available: bool = False


@dataclass(frozen=True)
class WriteSnapshot:
    """Token fingerprints inspected source/scope/targets and offered choices.

    Selections are checked against these facts; the first preview cannot
    fingerprint the user's as-yet-unknown decision. Generation is W-2.
    """
    items: tuple[WriteItemSnapshot, ...]
    preview_token: str
    inspection: WriteInspectionState | None = None


@dataclass(frozen=True)
class WriteOption:
    policy: WritePolicy
    target_uid: str | None = None
    reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.reasons


@dataclass(frozen=True)
class WriteChoice:
    item_key: str
    matches: tuple[WriteTarget, ...]
    options: tuple[WriteOption, ...]


@dataclass(frozen=True)
class WriteItemDecision:
    item_key: str
    action: WriteAction
    target_uid: str | None = None
    copy_system_name: str | None = None


@dataclass(frozen=True)
class WriteDecision:
    status: WriteStatus
    preview_token: str
    choices: tuple[WriteChoice, ...] = ()
    actions: tuple[WriteItemDecision, ...] = ()
    issues: tuple[str, ...] = ()
    stale: bool = False
