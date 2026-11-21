"""Read-only lifecycle predicates over ready, typed captured facts."""

from typing import Protocol, cast

from pydantic import BaseModel

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.application.lifecycle.contracts.preparationPolicy import LifecyclePreparationPolicy
from app.application.lifecycle.contracts.typedViews import PreparationRequest, preparation_view
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.reads.facts import LastTransitionFact
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle, UnknownLifecycle
from app.dataModel.lifecycle.results.issues import (
    LifecycleFieldCode as F, LifecycleRelationCode as R, LifecycleFieldIssue,
    LifecycleRelationIssue, LifecycleIssue,
)
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class _Reason(Protocol):
    reason_id: str
    action_uid: EntityUid
    operation: LifecycleOperation


class LifecycleTransitionValidator[Q: BaseModel, P: BaseModel]:
    def __init__(self, binding: LifecyclePreparationBinding[Q, P], policy: LifecyclePreparationPolicy) -> None:
        self._binding = binding
        self._policy = policy

    def validate_create(self, request: Q) -> tuple[LifecycleIssue, ...]:
        return self._validate(request, LifecycleOperation.CREATE)

    def validate_replacement(self, request: Q) -> tuple[LifecycleIssue, ...]:
        return self._validate(request, LifecycleOperation.REPLACEMENT)

    def validate_end(self, request: Q) -> tuple[LifecycleIssue, ...]:
        return self._validate(request, LifecycleOperation.END)

    def validate_reactivate(self, request: Q) -> tuple[LifecycleIssue, ...]:
        return self._validate(request, LifecycleOperation.REACTIVATE)

    def _validate(self, request: Q, operation: LifecycleOperation) -> tuple[LifecycleIssue, ...]:
        if self._binding.operation is not operation:
            raise TypeError("validator operation does not match its construction binding")
        return self._validate_typed(preparation_view(request), operation)

    def _validate_typed[T, Reason: BaseModel](
        self, request: PreparationRequest[T, Reason], operation: LifecycleOperation,
    ) -> tuple[LifecycleIssue, ...]:
        errors = ValidatorAggregationHelper[LifecycleIssue]((LifecycleFieldIssue, LifecycleRelationIssue))
        root = CheckedPath.root(type(request))
        intent_ref = FieldRef(lambda: type(request), lambda value: value.intent)
        capture_ref = FieldRef(lambda: type(request), lambda value: value.capture)
        admission_ref = FieldRef(lambda: type(request), lambda value: value.admission)
        intent = intent_ref.select(request)
        capture = capture_ref.select(request)
        admission = admission_ref.select(request)
        ip = root.field(intent_ref)
        cp = root.field(capture_ref)
        ap = root.field(admission_ref)
        entities_ref = FieldRef(lambda: type(capture), lambda value: value.entities)
        facts_ref = FieldRef(lambda: type(capture), lambda value: value.last_transitions)
        entities = entities_ref.select(capture)
        facts = facts_ref.select(capture)
        ep = cp.field(entities_ref)
        fp = cp.field(facts_ref)

        def field[A: BaseModel, B](code: F, path: CheckedPath[A, B], message: str) -> None:
            errors.add(LifecycleFieldIssue(code=code, path=path.freeze(), message=message))

        def relation[A: BaseModel, B, C: BaseModel, D](code: R, path: CheckedPath[A, B], message: str, related: CheckedPath[C, D] | None = None) -> None:
            errors.add(LifecycleRelationIssue(code=code, path=path.freeze(), message=message,
                                              related_path=related.freeze() if related is not None else None))

        if capture.publication != admission.publication:
            relation(R.BASE_MISMATCH, ap, "Admission and capture must use the same publication", cp)
        if capture.publication.active_timeline_id is None:
            relation(R.BASE_MISMATCH, cp, "A transition requires a captured timeline")

        replacement = operation is LifecycleOperation.REPLACEMENT
        if intent.operation is LifecycleOperation.REPLACEMENT:
            predecessors = intent.predecessors
            refs = predecessors + intent.successors
        else:
            predecessors = ()
            refs = (intent.entity,)
        predecessor_count = len(predecessors)
        seen: set[LifecycleEntityRef[T]] = set()
        for i, ref in enumerate(refs):
            if ref in seen:
                code = (R.PARTICIPANT_OVERLAP if replacement and i >= predecessor_count
                        and ref in predecessors else R.DUPLICATE_PARTICIPANT)
                relation(code, ip, "Participants must be unique and replacement sides disjoint")
            seen.add(ref)

        observations: dict[LifecycleEntityRef[T], AbsentLifecycle[T] | PresentLifecycle[T] | UnknownLifecycle[T]] = {}
        for index, observation in enumerate(entities):
            ref = observation.state.entity if isinstance(observation, PresentLifecycle) else observation.entity
            if ref in observations:
                relation(R.DUPLICATE_PARTICIPANT, ep.item(index), "Capture contains duplicate entity facts")
            else:
                observations[ref] = observation
            if isinstance(observation, PresentLifecycle):
                if observation.state.last_transition.world_uid != capture.publication.world_uid:
                    relation(R.IDENTITY_MISMATCH, ep.item(index), "State transition belongs to another world")

        fact_map: dict[LifecycleEntityRef[T], LastTransitionFact[T]] = {}
        for index, fact in enumerate(facts):
            if fact.entity in fact_map:
                relation(R.DUPLICATE_PARTICIPANT, fp.item(index), "Duplicate last-transition fact")
            else:
                fact_map[fact.entity] = fact
            if fact.ref.world_uid != capture.publication.world_uid:
                relation(R.IDENTITY_MISMATCH, fp.item(index), "Last-transition fact belongs to another world")

        for index, ref in enumerate(refs):
            observation = observations.get(ref)
            if observation is None:
                field(F.REQUIRED_FACT_MISSING, ep, "Entity observation was not captured")
                continue
            if isinstance(observation, UnknownLifecycle):
                field(F.UNKNOWN_FACT, ep, "Unknown observation cannot authorize a transition")
                continue
            creates = operation is LifecycleOperation.CREATE or (replacement and index >= predecessor_count)
            if creates:
                if not isinstance(observation, AbsentLifecycle):
                    field(F.INVALID_STATE, ep, "Creation requires confirmed absence")
                continue
            active = operation is not LifecycleOperation.REACTIVATE
            if not isinstance(observation, PresentLifecycle) or observation.state.active is not active:
                field(F.INVALID_STATE, ep, "Captured lifecycle activity does not permit this transition")
                continue
            if operation is LifecycleOperation.REACTIVATE:
                fact = fact_map.get(ref)
                if fact is None:
                    field(F.REQUIRED_FACT_MISSING, fp, "Reactivation requires a last-transition fact")
                elif fact.ref != observation.state.last_transition:
                    relation(R.IDENTITY_MISMATCH, fp, "Last-transition fact does not match the state", ep)
                elif fact.operation not in self._policy.reactivation_after:
                    field(F.REACTIVATION_RULE_UNSUPPORTED, fp, "This predecessor operation does not permit reactivation")

        reason = cast(_Reason, intent.reason)
        declaration = next((d for d in self._policy.reasons if d.reason_model is type(intent.reason)), None)
        if declaration is None or declaration.reason_id != reason.reason_id or any(
                declaration.entity_kind != ref.kind for ref in refs):
            field(F.UNSUPPORTED_REASON, ip, "Reason type/identifier/entity kind is not declared")
        if reason.operation is not operation:
            relation(R.REASON_OPERATION_MISMATCH, ip, "Reason refers to another lifecycle operation")
        if reason.action_uid != admission.action_uid:
            relation(R.ADMISSION_MISMATCH, ap, "Admission belongs to another subject action", ip)
        expected = tuple((ref, "end" if replacement and i < predecessor_count else
                          "create" if replacement else operation.value, reason.action_uid)
                         for i, ref in enumerate(refs))
        actual = tuple((effect.entity, effect.effect, effect.reason_action_uid) for effect in admission.effects)
        if len(set(actual)) != len(actual) or set(actual) != set(expected):
            relation(R.ADMISSION_MISMATCH, ap, "Admission must cover exactly the requested typed effects", ip)
        return errors.snapshot()
