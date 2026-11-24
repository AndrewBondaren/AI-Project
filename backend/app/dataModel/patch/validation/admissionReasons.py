"""Immutable admission facts. Compatibility facts can be exported by consumers."""
from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Literal, Self
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.validation.admissionCode import PatchSetAdmissionCode
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationInfo, field_validator, model_validator
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.values import FormatVersion
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation


class _AdmissionFact(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class _CompatibilityFact[C: PatchSetAdmissionCode](_AdmissionFact):
    code: C

    @model_validator(mode="before")
    @classmethod
    def reject_foreign_code_enum(cls, data: object) -> object:
        # Literal validation otherwise normalizes equal foreign enum members.
        if isinstance(data, Mapping):
            code = data.get(bind_field(_COMPATIBILITY_CODE).field)
        elif isinstance(data, _CompatibilityFact):
            code = _COMPATIBILITY_CODE.select(data)
        else:
            return data
        if isinstance(code, Enum) and type(code) is not PatchSetAdmissionCode:
            raise ValueError("code must not belong to a foreign enum")
        return data


_COMPATIBILITY_CODE = FieldRef[_CompatibilityFact[PatchSetAdmissionCode], PatchSetAdmissionCode](
    model=lambda: _CompatibilityFact[PatchSetAdmissionCode], select=lambda fact: fact.code)


class PatchSetRequestModelMismatch(_AdmissionFact):
    expected_model: ModelIdentity
    actual_type_name: StrictStr


class _Versions(_AdmissionFact):
    actual_version: FormatVersion
    supported_versions: tuple[FormatVersion, ...] = Field(min_length=1)

    @field_validator("supported_versions", mode="before")
    @classmethod
    def json_versions_tuple(cls, value: object, info: ValidationInfo) -> object:
        # A model-before guard materializes JSON arrays before strict tuple parsing.
        # Preserve JSON array support without admitting Python lists or coercing items.
        if info.mode == "json" and isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def ordered_versions(self) -> Self:
        if self.supported_versions != tuple(sorted(set(self.supported_versions))):
            raise ValueError("supported versions must be unique and ascending")
        return self


class PatchSetRequestVersionUnsupported(
    _Versions, _CompatibilityFact[Literal[PatchSetAdmissionCode.REQUEST_VERSION_UNSUPPORTED]]
):
    code: Literal[PatchSetAdmissionCode.REQUEST_VERSION_UNSUPPORTED]


class _SectionFact(_AdmissionFact):
    section_index: Annotated[StrictInt, Field(ge=0)]
    section_key: SectionKey


class PatchSetSectionKeyUnknown(
    _SectionFact, _CompatibilityFact[Literal[PatchSetAdmissionCode.SECTION_KEY_UNKNOWN]]
):
    code: Literal[PatchSetAdmissionCode.SECTION_KEY_UNKNOWN]


class PatchSetSectionModelMismatch(
    _SectionFact, _CompatibilityFact[Literal[PatchSetAdmissionCode.SECTION_MODEL_MISMATCH]]
):
    code: Literal[PatchSetAdmissionCode.SECTION_MODEL_MISMATCH]
    expected_model: ModelIdentity
    actual_type_name: StrictStr


class PatchSetSectionVersionUnsupported(
    _SectionFact, _Versions, _CompatibilityFact[Literal[PatchSetAdmissionCode.SECTION_VERSION_UNSUPPORTED]]
):
    code: Literal[PatchSetAdmissionCode.SECTION_VERSION_UNSUPPORTED]


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
