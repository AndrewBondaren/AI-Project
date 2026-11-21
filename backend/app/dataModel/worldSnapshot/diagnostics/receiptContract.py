"""Relations between an input section and its handler receipt."""
from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.worldSnapshot.metadata.metadataIssues import SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue


class ReceiptSectionMismatch(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    section_index: Annotated[StrictInt, Field(ge=0)]
    expected_section_key: SectionKey
    actual_section_key: SectionKey

    @model_validator(mode="after")
    def different_keys(self) -> Self:
        if self.expected_section_key == self.actual_section_key:
            raise ValueError("section mismatch requires different keys")
        return self


class ReceiptChangedPatchNotInInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    section_index: Annotated[StrictInt, Field(ge=0)]
    section_key: SectionKey
    changed_index: Annotated[StrictInt, Field(ge=0)]
    patch_ref: PatchRef


type ReceiptContractIssue = (ReceiptSectionMismatch | ReceiptChangedPatchNotInInput
                            | SnapshotMetadataFieldIssue | SnapshotMetadataRelationIssue)
