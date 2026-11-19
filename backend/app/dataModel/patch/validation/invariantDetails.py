"""Machine-readable reasons shared by model facts and assembly diagnostics."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.values import PatchOrdinal
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PatchSetInvariantCode(StrEnum):
    WORLD_MISMATCH = "patch_set.assembly.world_mismatch"
    MISSING_PACK = "patch_set.assembly.missing_pack"
    DUPLICATE_PLAYER = "patch_set.assembly.duplicate_player"
    DUPLICATE_SECTION = "patch_set.assembly.duplicate_section"
    MISSING_PREPARED_DEPENDENCY = "patch_set.assembly.missing_prepared_dependency"
    PREPARED_DEPENDENCY_ORDER = "patch_set.assembly.prepared_dependency_order"
    PATCH_OPERATION_MISMATCH = "patch_set.assembly.patch_operation_mismatch"
    PATCH_SECTION_MISMATCH = "patch_set.assembly.patch_section_mismatch"
    DUPLICATE_PATCH_ORDINAL = "patch_set.assembly.duplicate_patch_ordinal"


class WorldMismatchDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.WORLD_MISMATCH] = PatchSetInvariantCode.WORLD_MISMATCH
    expected_world_uid: EntityUid
    actual_world_uid: EntityUid


class MissingPackDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.MISSING_PACK] = PatchSetInvariantCode.MISSING_PACK
    publication: WorldPublicationRef


class DuplicatePlayerDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.DUPLICATE_PLAYER] = PatchSetInvariantCode.DUPLICATE_PLAYER
    player_uid: EntityUid


class DuplicateSectionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.DUPLICATE_SECTION] = PatchSetInvariantCode.DUPLICATE_SECTION
    section_key: SectionKey


class MissingPreparedDependencyDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.MISSING_PREPARED_DEPENDENCY] = PatchSetInvariantCode.MISSING_PREPARED_DEPENDENCY
    source_section_key: SectionKey
    missing_section_key: SectionKey


class PreparedDependencyOrderDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.PREPARED_DEPENDENCY_ORDER] = PatchSetInvariantCode.PREPARED_DEPENDENCY_ORDER
    source_section_key: SectionKey
    dependency_section_key: SectionKey


class PatchOperationMismatchDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.PATCH_OPERATION_MISMATCH] = PatchSetInvariantCode.PATCH_OPERATION_MISMATCH
    patch_ref: PatchRef
    expected_operation_id: EntityUid


class PatchSectionMismatchDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.PATCH_SECTION_MISMATCH] = PatchSetInvariantCode.PATCH_SECTION_MISMATCH
    patch_ref: PatchRef
    expected_section_key: SectionKey


class DuplicatePatchOrdinalDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    code: Literal[PatchSetInvariantCode.DUPLICATE_PATCH_ORDINAL] = PatchSetInvariantCode.DUPLICATE_PATCH_ORDINAL
    section_key: SectionKey
    ordinal: PatchOrdinal


type PatchSetInvariantDetails = Annotated[
    WorldMismatchDetails
    | MissingPackDetails
    | DuplicatePlayerDetails
    | DuplicateSectionDetails
    | MissingPreparedDependencyDetails
    | PreparedDependencyOrderDetails
    | PatchOperationMismatchDetails
    | PatchSectionMismatchDetails
    | DuplicatePatchOrdinalDetails,
    Field(discriminator="code"),
]
