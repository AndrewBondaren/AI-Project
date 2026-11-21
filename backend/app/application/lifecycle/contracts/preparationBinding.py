"""Immutable construction-time agreement between a request and its result."""

from dataclasses import dataclass, field
from types import UnionType
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel

from app.dataModel.fields.validatedFieldPath import is_model_identity_owner
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle, UnknownLifecycle, LastTransitionFact


def require_named_model(model: object) -> type[BaseModel]:
    if not is_model_identity_owner(model):
        raise TypeError("Lifecycle binding requires a named closed model")
    if any(model.model_config.get(key) != value for key, value in (
        ("strict", True), ("frozen", True), ("extra", "forbid"), ("revalidate_instances", "always")
    )):
        raise TypeError("Lifecycle models must be strict, frozen and always revalidated")
    return model


def nested_model(model: type[BaseModel], name: str) -> type[BaseModel]:
    return require_named_model(model.model_fields[name].annotation)


def tuple_item(model: type[BaseModel], name: str) -> object:
    annotation = model.model_fields[name].annotation
    args = get_args(annotation)
    if get_origin(annotation) is not tuple or len(args) != 2 or args[1] is not Ellipsis:
        raise TypeError(f"{name} must be an ordered immutable tuple")
    return args[0]


def union_members(annotation: object) -> tuple[object, ...]:
    return get_args(annotation) if get_origin(annotation) in (Union, UnionType) else (annotation,)


def model_extends(model: type[BaseModel], base: type[BaseModel]) -> bool:
    """Nominal check without erasing a closed class into an open generic."""
    return issubclass(model, base)


@dataclass(frozen=True, slots=True)
class LifecyclePreparationBinding[Q: BaseModel, P: BaseModel]:
    request_model: type[Q]
    prepared_model: type[P]
    intent_model: type[BaseModel] = field(init=False)
    transition_model: type[BaseModel] = field(init=False)
    participant_model: type[BaseModel] = field(init=False)
    state_model: type[BaseModel] = field(init=False)
    ref_model: type[BaseModel] = field(init=False)
    reason_model: type[BaseModel] = field(init=False)
    absent_model: type[BaseModel] = field(init=False)
    present_model: type[BaseModel] = field(init=False)
    operation: LifecycleOperation = field(init=False)

    def __post_init__(self) -> None:
        request = require_named_model(self.request_model)
        prepared = require_named_model(self.prepared_model)
        if set(request.model_fields) != {"intent", "capture", "admission"}:
            raise TypeError("request must contain intent/capture/admission")
        if set(prepared.model_fields) != {"base", "transition"}:
            raise TypeError("prepared must contain base/transition without a header")
        intent = nested_model(request, "intent")
        transition = nested_model(prepared, "transition")
        if nested_model(transition, "intent") is not intent:
            raise TypeError("request and prepared must share the exact intent class")
        operation_type = intent.model_fields["operation"].annotation
        operations = get_args(operation_type)
        if (get_origin(operation_type) is not Literal or len(operations) != 1
                or type(operations[0]) is not LifecycleOperation):
            raise TypeError("intent must bind one Lifecycle operation")
        operation = operations[0]
        ref = (require_named_model(tuple_item(intent, "predecessors"))
               if operation is LifecycleOperation.REPLACEMENT else nested_model(intent, "entity"))
        if not model_extends(ref, LifecycleEntityRef):
            raise TypeError("intent must contain a Lifecycle entity ref")
        if operation is LifecycleOperation.REPLACEMENT and tuple_item(intent, "successors") is not ref:
            raise TypeError("replacement sides must share the exact ref model")
        participant = require_named_model(tuple_item(transition, "participants"))
        state = nested_model(participant, "after")
        if nested_model(state, "entity") is not ref:
            raise TypeError("participant state has a different entity kind")
        before = tuple(require_named_model(m) for m in union_members(participant.model_fields["before"].annotation))
        absent = tuple(m for m in before if model_extends(m, AbsentLifecycle))
        present = tuple(m for m in before if model_extends(m, PresentLifecycle))
        if len(before) != 2 or len(absent) != 1 or len(present) != 1:
            raise TypeError("successful participant requires exact absent/present branches")
        if nested_model(absent[0], "entity") is not ref or nested_model(present[0], "state") is not state:
            raise TypeError("before and after have different identity/state schemas")
        capture = nested_model(request, "capture")
        observation_models = tuple(require_named_model(m) for m in union_members(tuple_item(capture, "entities")))
        if absent[0] not in observation_models or present[0] not in observation_models:
            raise TypeError("capture does not preserve the participant observation types")
        unknown = tuple(m for m in observation_models if model_extends(m, UnknownLifecycle))
        if len(observation_models) != 3 or len(unknown) != 1 or nested_model(unknown[0], "entity") is not ref:
            raise TypeError("capture must contain one same-kind unknown observation branch")
        last_fact = require_named_model(tuple_item(capture, "last_transitions"))
        if not model_extends(last_fact, LastTransitionFact) or nested_model(last_fact, "entity") is not ref:
            raise TypeError("last-transition facts must retain the same entity kind")
        admission = nested_model(request, "admission")
        effect = require_named_model(tuple_item(admission, "effects"))
        if nested_model(effect, "entity") is not ref:
            raise TypeError("admission effects have a different entity kind")
        reason = nested_model(intent, "reason")
        if not {"reason_id", "action_uid", "operation"} <= set(reason.model_fields):
            raise TypeError("local reason evidence requires declared identity/action/operation fields")
        for name, value in (
            ("intent_model", intent), ("transition_model", transition),
            ("participant_model", participant), ("state_model", state), ("ref_model", ref),
            ("reason_model", reason), ("absent_model", absent[0]),
            ("present_model", present[0]), ("operation", operation),
        ):
            object.__setattr__(self, name, value)

    def admit(self, request: Q) -> Q:
        if type(request) is not self.request_model:
            raise TypeError("request does not have the exact bound class")
        return self.request_model.model_validate(request, strict=True)
