"""Builds a named transition only after successful lifecycle validation."""

from pydantic import BaseModel

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.reads.facts import PresentLifecycle


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
        intent = request.intent
        base = request.capture.publication
        transition_ref = LifecycleTransitionRef(world_uid=base.world_uid,
            origin_timeline_id=base.active_timeline_id, change_uid=intent.change_uid)
        observations = {
            (fact.state.entity if isinstance(fact, PresentLifecycle) else fact.entity): fact
            for fact in request.capture.entities
        }
        replacement = operation is LifecycleOperation.REPLACEMENT
        refs = intent.predecessors + intent.successors if replacement else (intent.entity,)
        participants = tuple(self._binding.participant_model(
            before=observations[ref], after=self._binding.state_model(
                entity=ref, active=(index >= len(intent.predecessors) if replacement
                                    else operation is not LifecycleOperation.END),
                last_transition=transition_ref)) for index, ref in enumerate(refs))
        transition = self._binding.transition_model(intent=intent, participants=participants)
        return self._binding.prepared_model(base=base, transition=transition)
