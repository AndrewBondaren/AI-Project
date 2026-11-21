"""Closed synthetic A/B schemas for the mock Lifecycle world only."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.entityLifecycle import EntityLifecycle
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.operations.intents import LifecycleCreate, LifecycleReplacement, LifecycleEnd, LifecycleReactivate
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle, UnknownLifecycle, LastTransitionFact
from app.dataModel.lifecycle.reads.capture import LifecycleCapture
from app.dataModel.lifecycle.evidence.effects import DomainEffect
from app.dataModel.lifecycle.evidence.admission import DomainAdmission
from app.dataModel.lifecycle.evidence.coverage import PreparedEffectBinding
from app.dataModel.lifecycle.changes.participant import ParticipantTransition
from app.dataModel.lifecycle.changes.transition import LifecycleTransition
from app.dataModel.lifecycle.publication.patch import LifecycleTransitionPatch
from app.dataModel.lifecycle.publication.section import LifecycleSection
from app.dataModel.lifecycle.publication.prepareSection import PrepareLifecycleSection
from app.dataModel.lifecycle.operations.create import PrepareLifecycleCreate
from app.dataModel.lifecycle.changes.preparedCreate import PreparedLifecycleCreate
from app.dataModel.lifecycle.operations.replacement import PrepareLifecycleReplacement
from app.dataModel.lifecycle.changes.preparedReplacement import PreparedLifecycleReplacement
from app.dataModel.lifecycle.operations.end import PrepareLifecycleEnd
from app.dataModel.lifecycle.changes.preparedEnd import PreparedLifecycleEnd
from app.dataModel.lifecycle.operations.reactivate import PrepareLifecycleReactivate
from app.dataModel.lifecycle.changes.preparedReactivate import PreparedLifecycleReactivate

TestEntityA = Literal["test_entity_a"]


class TestAReason(BaseModel):
    __test__ = False
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    reason_id: Literal["test_a_action"]
    action_uid: EntityUid
    operation: LifecycleOperation


class RefA(LifecycleEntityRef[TestEntityA]):
    pass


class EntityStateA(EntityLifecycle[TestEntityA]):
    entity: RefA


class AbsentA(AbsentLifecycle[TestEntityA]):
    entity: RefA


class PresentA(PresentLifecycle[TestEntityA]):
    state: EntityStateA


class UnknownA(UnknownLifecycle[TestEntityA]):
    entity: RefA


class LastTransitionFactA(LastTransitionFact[TestEntityA]):
    entity: RefA


class CaptureA(LifecycleCapture[TestEntityA]):
    entities: tuple[AbsentA | PresentA | UnknownA, ...]
    last_transitions: tuple[LastTransitionFactA, ...]


class EffectA(DomainEffect[TestEntityA]):
    entity: RefA


class AdmissionA(DomainAdmission[TestEntityA]):
    effects: tuple[EffectA, ...] = Field(min_length=1)


class CoverageA(PreparedEffectBinding[TestEntityA]):
    effect: EffectA


class ParticipantA(ParticipantTransition[TestEntityA]):
    before: AbsentA | PresentA
    after: EntityStateA


class CreateIntentA(LifecycleCreate[TestEntityA, TestAReason]):
    entity: RefA
    reason: TestAReason


class CreateRequestA(PrepareLifecycleCreate[TestEntityA, TestAReason]):
    intent: CreateIntentA
    capture: CaptureA
    admission: AdmissionA


class CreateTransitionA(LifecycleTransition[TestEntityA, CreateIntentA]):
    intent: CreateIntentA
    participants: tuple[ParticipantA, ...] = Field(min_length=1)


class CreateA(PreparedLifecycleCreate[TestEntityA, TestAReason]):
    transition: CreateTransitionA


class CreatePatchA(LifecycleTransitionPatch[CreateA]):
    prepared: CreateA


class ReplaceIntentA(LifecycleReplacement[TestEntityA, TestAReason]):
    predecessors: tuple[RefA, ...] = Field(min_length=1)
    successors: tuple[RefA, ...] = Field(min_length=1)
    reason: TestAReason


class ReplaceRequestA(PrepareLifecycleReplacement[TestEntityA, TestAReason]):
    intent: ReplaceIntentA
    capture: CaptureA
    admission: AdmissionA


class ReplaceTransitionA(LifecycleTransition[TestEntityA, ReplaceIntentA]):
    intent: ReplaceIntentA
    participants: tuple[ParticipantA, ...] = Field(min_length=1)


class ReplaceA(PreparedLifecycleReplacement[TestEntityA, TestAReason]):
    transition: ReplaceTransitionA


class ReplacePatchA(LifecycleTransitionPatch[ReplaceA]):
    prepared: ReplaceA


class EndIntentA(LifecycleEnd[TestEntityA, TestAReason]):
    entity: RefA
    reason: TestAReason


class EndRequestA(PrepareLifecycleEnd[TestEntityA, TestAReason]):
    intent: EndIntentA
    capture: CaptureA
    admission: AdmissionA


class EndTransitionA(LifecycleTransition[TestEntityA, EndIntentA]):
    intent: EndIntentA
    participants: tuple[ParticipantA, ...] = Field(min_length=1)


class EndA(PreparedLifecycleEnd[TestEntityA, TestAReason]):
    transition: EndTransitionA


class EndPatchA(LifecycleTransitionPatch[EndA]):
    prepared: EndA


class ReactivateIntentA(LifecycleReactivate[TestEntityA, TestAReason]):
    entity: RefA
    reason: TestAReason


class ReactivateRequestA(PrepareLifecycleReactivate[TestEntityA, TestAReason]):
    intent: ReactivateIntentA
    capture: CaptureA
    admission: AdmissionA


class ReactivateTransitionA(LifecycleTransition[TestEntityA, ReactivateIntentA]):
    intent: ReactivateIntentA
    participants: tuple[ParticipantA, ...] = Field(min_length=1)


class ReactivateA(PreparedLifecycleReactivate[TestEntityA, TestAReason]):
    transition: ReactivateTransitionA


class ReactivatePatchA(LifecycleTransitionPatch[ReactivateA]):
    prepared: ReactivateA

TestEntityB = Literal["test_entity_b"]


class TestBReason(BaseModel):
    __test__ = False
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    reason_id: Literal["test_b_action"]
    action_uid: EntityUid
    operation: LifecycleOperation


class RefB(LifecycleEntityRef[TestEntityB]):
    pass


class EntityStateB(EntityLifecycle[TestEntityB]):
    entity: RefB


class AbsentB(AbsentLifecycle[TestEntityB]):
    entity: RefB


class PresentB(PresentLifecycle[TestEntityB]):
    state: EntityStateB


class UnknownB(UnknownLifecycle[TestEntityB]):
    entity: RefB


class LastTransitionFactB(LastTransitionFact[TestEntityB]):
    entity: RefB


class CaptureB(LifecycleCapture[TestEntityB]):
    entities: tuple[AbsentB | PresentB | UnknownB, ...]
    last_transitions: tuple[LastTransitionFactB, ...]


class EffectB(DomainEffect[TestEntityB]):
    entity: RefB


class AdmissionB(DomainAdmission[TestEntityB]):
    effects: tuple[EffectB, ...] = Field(min_length=1)


class CoverageB(PreparedEffectBinding[TestEntityB]):
    effect: EffectB


class ParticipantB(ParticipantTransition[TestEntityB]):
    before: AbsentB | PresentB
    after: EntityStateB


class CreateIntentB(LifecycleCreate[TestEntityB, TestBReason]):
    entity: RefB
    reason: TestBReason


class CreateRequestB(PrepareLifecycleCreate[TestEntityB, TestBReason]):
    intent: CreateIntentB
    capture: CaptureB
    admission: AdmissionB


class CreateTransitionB(LifecycleTransition[TestEntityB, CreateIntentB]):
    intent: CreateIntentB
    participants: tuple[ParticipantB, ...] = Field(min_length=1)


class CreateB(PreparedLifecycleCreate[TestEntityB, TestBReason]):
    transition: CreateTransitionB


class CreatePatchB(LifecycleTransitionPatch[CreateB]):
    prepared: CreateB


class ReplaceIntentB(LifecycleReplacement[TestEntityB, TestBReason]):
    predecessors: tuple[RefB, ...] = Field(min_length=1)
    successors: tuple[RefB, ...] = Field(min_length=1)
    reason: TestBReason


class ReplaceRequestB(PrepareLifecycleReplacement[TestEntityB, TestBReason]):
    intent: ReplaceIntentB
    capture: CaptureB
    admission: AdmissionB


class ReplaceTransitionB(LifecycleTransition[TestEntityB, ReplaceIntentB]):
    intent: ReplaceIntentB
    participants: tuple[ParticipantB, ...] = Field(min_length=1)


class ReplaceB(PreparedLifecycleReplacement[TestEntityB, TestBReason]):
    transition: ReplaceTransitionB


class ReplacePatchB(LifecycleTransitionPatch[ReplaceB]):
    prepared: ReplaceB


class EndIntentB(LifecycleEnd[TestEntityB, TestBReason]):
    entity: RefB
    reason: TestBReason


class EndRequestB(PrepareLifecycleEnd[TestEntityB, TestBReason]):
    intent: EndIntentB
    capture: CaptureB
    admission: AdmissionB


class EndTransitionB(LifecycleTransition[TestEntityB, EndIntentB]):
    intent: EndIntentB
    participants: tuple[ParticipantB, ...] = Field(min_length=1)


class EndB(PreparedLifecycleEnd[TestEntityB, TestBReason]):
    transition: EndTransitionB


class EndPatchB(LifecycleTransitionPatch[EndB]):
    prepared: EndB


class ReactivateIntentB(LifecycleReactivate[TestEntityB, TestBReason]):
    entity: RefB
    reason: TestBReason


class ReactivateRequestB(PrepareLifecycleReactivate[TestEntityB, TestBReason]):
    intent: ReactivateIntentB
    capture: CaptureB
    admission: AdmissionB


class ReactivateTransitionB(LifecycleTransition[TestEntityB, ReactivateIntentB]):
    intent: ReactivateIntentB
    participants: tuple[ParticipantB, ...] = Field(min_length=1)


class ReactivateB(PreparedLifecycleReactivate[TestEntityB, TestBReason]):
    transition: ReactivateTransitionB


class ReactivatePatchB(LifecycleTransitionPatch[ReactivateB]):
    prepared: ReactivateB

PreparedAB = CreateA | ReplaceA | EndA | ReactivateA | CreateB | ReplaceB | EndB | ReactivateB
PatchAB = CreatePatchA | ReplacePatchA | EndPatchA | ReactivatePatchA | CreatePatchB | ReplacePatchB | EndPatchB | ReactivatePatchB
CoverageAB = CoverageA | CoverageB


class PrepareLifecycleSectionAB(PrepareLifecycleSection[PreparedAB, CoverageAB]):
    changes: tuple[PreparedAB, ...] = Field(min_length=1)
    domain_evidence: tuple[CoverageAB, ...]


class LifecycleSectionAB(LifecycleSection[PatchAB, CoverageAB]):
    patches: tuple[PatchAB, ...] = Field(min_length=1)
    domain_evidence: tuple[CoverageAB, ...]
