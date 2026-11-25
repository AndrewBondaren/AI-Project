"""Closed mock-only envelopes for the common write CALL chain."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from tests.lifecycle.support.domainSections import TestDomainSectionA
from tests.lifecycle.support.mixedContracts import PrepareLifecycleSectionAB
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockSnapshotApplyResult


class MockAssemblyContext(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    format_version: FormatVersion
    operation_id: EntityUid
    preparation_fingerprint: RevisionHex
    world_uid: EntityUid
    timeline_id: EntityUid
    turn_id: Annotated[StrictInt, Field(ge=1)]
    expected_world: WorldPublicationRef
    expected_players: tuple[PlayerHeadExpectation, ...]


class MockPrepareChangesInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    section_request: PrepareLifecycleSectionAB
    subject_section: TestDomainSectionA
    assembly_context: MockAssemblyContext


class MockPrepareChangesOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: MockAssemblyInput | LifecycleSectionRefused


class MockWriteChangesInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    preparation: MockPrepareChangesInput


class MockWriteChangesOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: MockSnapshotApplyResult | LifecycleSectionRefused | PatchSetAssemblyRefused


class MockWriteChangesState(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    stage: Literal["prepare", "assemble", "apply"]
    request: MockWriteChangesInput
