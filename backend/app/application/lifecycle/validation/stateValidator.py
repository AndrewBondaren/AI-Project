"""Authoritative retry and before-state predicates; no reads or writes."""
from typing import cast
from pydantic import BaseModel
from app.application.lifecycle.changes.semanticEquality import equivalent_transition
from app.application.lifecycle.contracts.typedViews import Prepared, Transition
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.lifecycle.identity import LifecycleEntityRef, LifecycleTransitionRef
from app.dataModel.lifecycle.publication.patch import LifecycleTransitionPatch
from app.dataModel.lifecycle.publication.section import LifecycleSection
from app.dataModel.lifecycle.evidence.coverage import PreparedEffectBinding
from app.dataModel.lifecycle.reads.capture import LifecycleCapture
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangeAbsent, AcceptedChangeFound, AcceptedChangesResult
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyIssue, LifecycleApplyCode
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionRefused
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind

type Native = LifecycleSection[LifecycleTransitionPatch[Prepared[object, BaseModel]], PreparedEffectBinding[object]]
type Lookup = AcceptedChangesResult[AcceptedChangeAbsent | AcceptedChangeFound[Transition]]


class LifecycleStateValidator[F: SectionRefused[LifecycleApplyIssue]]:
    def __init__(self, refusal_model: type[F]) -> None:
        self._refusal_model = refusal_model

    def validate(
        self, section: BaseModel, *, accepted: BaseModel,
        captures: tuple[BaseModel, ...], expected_world: WorldPublicationRef,
    ) -> SectionAccepted | F:
        section_model, lookup_model = type(section), type(accepted)
        if not isinstance(section, LifecycleSection) or not isinstance(accepted, AcceptedChangesResult):
            raise TypeError("state validation requires native Lifecycle section and accepted lookup")
        native = cast(Native, section_model.model_validate(section, strict=True))
        lookup = cast(Lookup, lookup_model.model_validate(accepted, strict=True))
        if expected_world.active_timeline_id is None:
            raise ValueError("Lifecycle requires an active timeline")
        refs = tuple(LifecycleTransitionRef(world_uid=expected_world.world_uid,
            origin_timeline_id=expected_world.active_timeline_id,
            change_uid=patch.prepared.transition.intent.change_uid) for patch in native.patches)
        if lookup.publication != expected_world or tuple(entry.ref for entry in lookup.entries) != refs:
            raise ValueError("accepted lookup must have exact publication, order and coverage")
        if len(set(refs)) != len(refs):
            raise ValueError("native section repeats a change identity")
        required: set[LifecycleEntityRef[object]] = set()
        for patch in native.patches:
            required.update(participant.after.entity for participant in patch.prepared.transition.participants)
        observations: dict[LifecycleEntityRef[object], AbsentLifecycle[object] | PresentLifecycle[object]] = {}
        kinds: set[object] = set()
        for raw in captures:
            capture_model = type(raw)
            if not isinstance(raw, LifecycleCapture):
                raise TypeError("current reader must return Lifecycle captures")
            capture = cast(LifecycleCapture[object], capture_model.model_validate(raw, strict=True))
            if capture.publication != expected_world or not capture.entities:
                raise ValueError("current capture has a different publication or empty coverage")
            local_kind: object = None
            for fact in capture.entities:
                if fact.status == "unknown":
                    raise ValueError("unknown authoritative Lifecycle observation")
                entity = fact.state.entity if fact.status == "present" else fact.entity
                if entity in observations:
                    raise ValueError("duplicate current entity observation")
                if local_kind is None:
                    local_kind = entity.kind
                elif entity.kind != local_kind:
                    raise ValueError("one current capture must represent one entity kind")
                observations[entity] = fact
            if local_kind in kinds:
                raise ValueError("duplicate current capture kind")
            kinds.add(local_kind)
        if set(observations) != required:
            raise ValueError("current capture must cover exactly the requested entities")

        errors = ValidatorAggregationHelper[LifecycleApplyIssue]((LifecycleApplyIssue,))
        patches_ref = FieldRef(lambda: type(native), lambda value: value.patches)
        patches_path = CheckedPath.root(type(native)).field(patches_ref)
        for index, (patch, entry) in enumerate(zip(native.patches, lookup.entries, strict=True)):
            prepared = patch.prepared
            if prepared.base != expected_world:
                raise ValueError("native Lifecycle base differs from the admitted publication")
            transition = prepared.transition
            prepared_ref = FieldRef(lambda: type(patch), lambda value: value.prepared)
            prepared_path = patches_path.item(index).variant(type(patch)).field(prepared_ref)
            transition_ref = FieldRef(lambda: type(prepared), lambda value: value.transition)
            transition_path = prepared_path.field(transition_ref)
            if entry.kind == "found":
                if entry.ref.change_uid != entry.transition.intent.change_uid:
                    raise ValueError("accepted index ref differs from its stored transition")
                if not equivalent_transition(transition, entry.transition):
                    intent_ref = FieldRef(lambda: type(transition), lambda value: value.intent)
                    uid_ref = FieldRef(lambda: type(transition.intent), lambda value: value.change_uid)
                    errors.add(LifecycleApplyIssue(code=LifecycleApplyCode.CHANGE_PAYLOAD_CONFLICT,
                        path=transition_path.field(intent_ref).field(uid_ref).freeze(),
                        message="Change identity already belongs to a different accepted transition"))
                continue
            participants_ref = FieldRef(lambda: type(transition), lambda value: value.participants)
            participants_path = transition_path.field(participants_ref)
            for ordinal, participant in enumerate(transition.participants):
                if observations[participant.after.entity] != participant.before:
                    before_ref = FieldRef(lambda: type(participant), lambda value: value.before)
                    errors.add(LifecycleApplyIssue(code=LifecycleApplyCode.BEFORE_STATE_MISMATCH,
                        path=participants_path.item(ordinal).field(before_ref).freeze(),
                        message="New transition before-state differs from the authoritative publication"))
        issues = errors.snapshot()
        return (self._refusal_model(category=SnapshotApplyOutcomeKind.CONFLICT, diagnostics=issues)
                if issues else SectionAccepted())
