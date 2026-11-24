"""Immutable admission facts. Compatibility facts can be exported by consumers."""
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.values import FormatVersion
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation


class _AdmissionFact(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class PatchSetRequestModelMismatch(_AdmissionFact):
    expected_model: ModelIdentity
    actual_type_name: StrictStr


class _Versions(_AdmissionFact):
    actual_version: FormatVersion
    supported_versions: tuple[FormatVersion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_versions(self) -> Self:
        if self.supported_versions != tuple(sorted(set(self.supported_versions))):
            raise ValueError("supported versions must be unique and ascending")
        return self


class PatchSetRequestVersionUnsupported(_Versions):
    code: Literal["patch_set.admission.request_version_unsupported"]


class _SectionFact(_AdmissionFact):
    section_index: Annotated[StrictInt, Field(ge=0)]
    section_key: SectionKey


class PatchSetSectionKeyUnknown(_SectionFact):
    code: Literal["patch_set.admission.section_key_unknown"]


class PatchSetSectionModelMismatch(_SectionFact):
    code: Literal["patch_set.admission.section_model_mismatch"]
    expected_model: ModelIdentity
    actual_type_name: StrictStr


class PatchSetSectionVersionUnsupported(_SectionFact, _Versions):
    code: Literal["patch_set.admission.section_version_unsupported"]


class PatchSetStructuralFailure(_AdmissionFact):
    error_type: PatchSetStructuralErrorKind
    loc: tuple[StrictStr | StrictInt, ...]
    message: StrictStr


PatchSetCompatibilityIssue = (PatchSetRequestVersionUnsupported | PatchSetSectionKeyUnknown
    | PatchSetSectionModelMismatch | PatchSetSectionVersionUnsupported)
PatchSetAdmissionReason = (PatchSetRequestModelMismatch | PatchSetCompatibilityIssue
    | PatchSetStructuralFailure | PatchSetInvariantViolation)
ADMISSION_REASON_TYPES = (PatchSetRequestModelMismatch, PatchSetRequestVersionUnsupported,
    PatchSetSectionKeyUnknown, PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported,
    PatchSetStructuralFailure, PatchSetInvariantViolation)
