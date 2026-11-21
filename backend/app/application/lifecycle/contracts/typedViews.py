"""Read-only type erasure after exact named-model admission.

These aliases describe existing POJOs; they neither construct replacement
records nor select public operations by payload.
"""
from typing import Protocol, cast
from pydantic import BaseModel
from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.operations.intents import LifecycleCreate, LifecycleEnd, LifecycleReactivate
from app.dataModel.lifecycle.lifecycleReplacement import LifecycleReplacement
from app.dataModel.lifecycle.operations.create import PrepareLifecycleCreate
from app.dataModel.lifecycle.operations.end import PrepareLifecycleEnd
from app.dataModel.lifecycle.operations.reactivate import PrepareLifecycleReactivate
from app.dataModel.lifecycle.operations.replacement import PrepareLifecycleReplacement
from app.dataModel.lifecycle.changes.preparedCreate import PreparedLifecycleCreate
from app.dataModel.lifecycle.changes.preparedEnd import PreparedLifecycleEnd
from app.dataModel.lifecycle.changes.preparedReactivate import PreparedLifecycleReactivate
from app.dataModel.lifecycle.changes.preparedReplacement import PreparedLifecycleReplacement
from app.dataModel.lifecycle.changes.transition import LifecycleTransition
from app.dataModel.lifecycle.evidence.coverage import PreparedEffectBinding
from app.dataModel.lifecycle.publication.prepareSection import PrepareLifecycleSection


type Intent[T, R: BaseModel] = LifecycleCreate[T, R] | LifecycleEnd[T, R] | LifecycleReactivate[T, R] | LifecycleReplacement[T, R]
type PreparationRequest[T, R: BaseModel] = PrepareLifecycleCreate[T, R] | PrepareLifecycleEnd[T, R] | PrepareLifecycleReactivate[T, R] | PrepareLifecycleReplacement[T, R]
type Prepared[T, R: BaseModel] = PreparedLifecycleCreate[T, R] | PreparedLifecycleEnd[T, R] | PreparedLifecycleReactivate[T, R] | PreparedLifecycleReplacement[T, R]
type SectionRequest = PrepareLifecycleSection[Prepared[object, BaseModel], PreparedEffectBinding[object]]
type Transition = LifecycleTransition[object, Intent[object, BaseModel]]


class ReasonView(Protocol):
    @property
    def reason_id(self) -> str: ...
    @property
    def action_uid(self) -> EntityUid: ...
    @property
    def operation(self) -> LifecycleOperation: ...


def preparation_view(request: BaseModel) -> PreparationRequest[object, BaseModel]:
    if not isinstance(request, (PrepareLifecycleCreate, PrepareLifecycleEnd, PrepareLifecycleReactivate, PrepareLifecycleReplacement)):
        raise TypeError("expected an owning Lifecycle preparation model")
    return cast(PreparationRequest[object, BaseModel], request)


def section_request_view(request: BaseModel) -> SectionRequest:
    if not isinstance(request, PrepareLifecycleSection):
        raise TypeError("expected an owning Lifecycle section request")
    return cast(SectionRequest, request)


def transition_view(transition: BaseModel) -> Transition:
    if not isinstance(transition, LifecycleTransition):
        raise TypeError("expected an owning Lifecycle transition")
    result = cast(Transition, transition)
    intent: object = cast(LifecycleTransition[object, BaseModel], transition).intent
    if not isinstance(intent, (LifecycleCreate, LifecycleEnd, LifecycleReactivate, LifecycleReplacement)):
        raise TypeError("expected an owning Lifecycle intent")
    return result
