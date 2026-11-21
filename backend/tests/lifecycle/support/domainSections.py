"""Synthetic subject payload and diagnostics; no runtime subject behavior."""
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.lifecycle.support.mixedContracts import RefA, RefB, EffectA, EffectB


class MockSubjectCode(StrEnum):
    INVALID_MUTATION = "invalid_mutation"
    EFFECT_PAYLOAD_MISMATCH = "effect_payload_mismatch"
    INCOMPLETE_EFFECT = "incomplete_effect"
    SUBJECT_BEFORE_MISMATCH = "subject_before_mismatch"


class MockSubjectIssue(FieldPathError[MockSubjectCode]):
    pass


class MockMutationA(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    entity: RefA
    slot: Literal["primary", "index"]
    before: bool | None
    after: bool
    action_uid: EntityUid


class TestDomainPatchA(PatchData):
    __test__ = False
    base: WorldPublicationRef
    mutations: tuple[MockMutationA, ...] = Field(min_length=1)
    effects: tuple[EffectA, ...] = Field(min_length=1)


class TestDomainSectionA(DomainSection[TestDomainPatchA]):
    __test__ = False
    patches: tuple[TestDomainPatchA, ...] = Field(min_length=1)


class MockMutationB(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    entity: RefB
    slot: Literal["primary", "index"]
    before: bool | None
    after: bool
    action_uid: EntityUid


class TestDomainPatchB(PatchData):
    __test__ = False
    base: WorldPublicationRef
    mutations: tuple[MockMutationB, ...] = Field(min_length=1)
    effects: tuple[EffectB, ...] = Field(min_length=1)


class TestDomainSectionB(DomainSection[TestDomainPatchB]):
    __test__ = False
    patches: tuple[TestDomainPatchB, ...] = Field(min_length=1)
