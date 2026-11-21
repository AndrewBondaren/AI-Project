"""Builds a named transition only after successful lifecycle validation."""

from typing import cast

from pydantic import BaseModel

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.operations.create import PrepareLifecycleCreate
from app.dataModel.lifecycle.operations.replacement import PrepareLifecycleReplacement
from app.dataModel.lifecycle.operations.end import PrepareLifecycleEnd
from app.dataModel.lifecycle.operations.reactivate import PrepareLifecycleReactivate


type PreparationRequest[T, R: BaseModel] = (
    PrepareLifecycleCreate[T, R] | PrepareLifecycleReplacement[T, R]
    | PrepareLifecycleEnd[T, R] | PrepareLifecycleReactivate[T, R]
)


class LifecycleChangeBuilder[Q: BaseModel, P: BaseModel]:
    def __init__(self, binding: LifecyclePreparationBinding[Q, P]) -> None:
        self._binding = binding

    def build_create(self, request: Q) -> P:
        return self._build(request, LifecycleOperation.CREATE)

    def build_replacement(self, request: Q) -> P:
        return self._build(request, LifecycleOperation.REPLACEMENT)

    def build_end(self, request: Q) -> P:
        return self._build(request, LifecycleOperation.END)

    def build_reactivate(self, request: Q) -> P:
        return self._build(request, LifecycleOperation.REACTIVATE)

    def _build(self, request: Q, operation: LifecycleOperation) -> P:
        if self._binding.operation is not operation:
            raise TypeError("builder operation does not match its binding")
        admitted = self._binding.admit(request)
        if not isinstance(admitted, (
            PrepareLifecycleCreate, PrepareLifecycleReplacement,
            PrepareLifecycleEnd, PrepareLifecycleReactivate,
        )):
            raise TypeError("builder requires an owning lifecycle preparation request")
        # Exact Q/P and their same-kind nested chain are checked by the binding.
        # Erase only the kind/reason specialization at this read-only boundary;
        # the algorithm below retains the owning request structure.
        return self._build_typed(cast(PreparationRequest[object, BaseModel], admitted))

    def _build_typed[T, R: BaseModel](self, request: PreparationRequest[T, R]) -> P:
        intent = request.intent
        base = request.capture.publication
        if base.active_timeline_id is None:
            raise ValueError("validated lifecycle request requires an active timeline")
        transition_ref = LifecycleTransitionRef(world_uid=base.world_uid,
            origin_timeline_id=base.active_timeline_id, change_uid=intent.change_uid)
        observations = {
            (fact.state.entity if fact.status == "present" else fact.entity): fact
            for fact in request.capture.entities
        }
        if intent.operation is LifecycleOperation.REPLACEMENT:
            refs = intent.predecessors + intent.successors
            active_from = len(intent.predecessors)
        else:
            refs = (intent.entity,)
            active_from = 1 if intent.operation is LifecycleOperation.END else 0
        participants = tuple(self._binding.participant_model(
            before=observations[ref], after=self._binding.state_model(
                entity=ref, active=index >= active_from,
                last_transition=transition_ref)) for index, ref in enumerate(refs))
        transition = self._binding.transition_model(intent=intent, participants=participants)
        return self._binding.prepared_model(base=base, transition=transition)
