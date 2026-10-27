"""Typed field bindings for scalar, observed and priority policy inputs."""

from dataclasses import dataclass
from typing import Annotated, Generic, Literal, Protocol, TypeAlias, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypeAliasType

from app.dataModel.cascade.cascadeGraph import BoundField, bind_field
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.policyFacts import FactValue, KnownFact, UnknownFact, WaitingFact

M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")


def _field(ref: object) -> BoundField:
    if not isinstance(ref, FieldRef):
        raise ValueError("policy reference requires FieldRef")
    bound = bind_field(ref)
    config = bound.model.model_config
    if not config.get("frozen") or config.get("extra") != "forbid" or config.get("revalidate_instances") != "always":
        raise ValueError("policy FieldRef source requires frozen, extra-forbid, revalidated BaseModel")
    return bound


def _fact_value_type(annotation: object) -> object:
    if get_origin(annotation) is FactValue:
        return get_args(annotation)[0]
    if get_origin(annotation) is Annotated:
        return _fact_value_type(get_args(annotation)[0])
    members = get_args(annotation)
    known = [member for member in members if isinstance(member, type) and issubclass(member, KnownFact)]
    if len(known) != 1 or set(members) != {known[0], WaitingFact, UnknownFact}:
        raise ValueError("fact reference requires FactValue[T], not a direct scalar")
    return known[0].model_fields["value"].rebuild_annotation()


def _plain(annotation: object) -> object:
    if isinstance(annotation, TypeAliasType):
        return _plain(annotation.__value__)
    if get_origin(annotation) is Annotated:
        return _plain(get_args(annotation)[0])
    return annotation


class PolicyReference(Protocol):
    @property
    def bound_field(self) -> BoundField: ...

    @property
    def value_annotation(self) -> object: ...


@dataclass(frozen=True)
class DirectValueRef(Generic[M, T]):
    field: FieldRef[M, T]

    def __post_init__(self) -> None:
        bound = _field(self.field)
        annotation = bound.model.model_fields[bound.field].annotation
        # FactValue must enter through its distinct, statically checked wrapper.
        if get_origin(annotation) is FactValue or any(
                isinstance(member, type) and issubclass(member, KnownFact) for member in get_args(annotation)):
            raise ValueError("FactValue source requires FactValueRef")

    @property
    def bound_field(self) -> BoundField:
        return _field(self.field)

    @property
    def value_annotation(self) -> object:
        bound = self.bound_field
        return bound.model.model_fields[bound.field].rebuild_annotation()


@dataclass(frozen=True)
class FactValueRef(Generic[M, T]):
    field: FieldRef[M, FactValue[T]]

    def __post_init__(self) -> None:
        self.value_annotation

    @property
    def bound_field(self) -> BoundField:
        return _field(self.field)

    @property
    def value_annotation(self) -> object:
        bound = self.bound_field
        return _fact_value_type(bound.model.model_fields[bound.field].annotation)


PolicyValueRef: TypeAlias = Union[DirectValueRef[M, T], FactValueRef[M, T]]


class PriorityReference(PolicyReference, Protocol):
    """Erasure point after the invariant typed FieldRef constructor checked M."""

    @property
    def is_priority(self) -> Literal[True]: ...


@dataclass(frozen=True)
class PriorityValueRef(Generic[M]):
    field: FieldRef[M, Specificity] | FieldRef[M, Specificity | None]

    def __post_init__(self) -> None:
        bound = _field(self.field)
        annotation = _plain(bound.model.model_fields[bound.field].annotation)
        members = {_plain(member) for member in get_args(annotation)}
        if annotation is not int and members != {int, type(None)}:
            raise ValueError("priority reference requires Specificity or nullable Specificity")
        adapter = TypeAdapter[object](self.value_annotation)
        adapter.validate_python(0, strict=True)
        try:
            adapter.validate_python(-1, strict=True)
        except ValueError:
            return
        raise ValueError("priority field must enforce nonnegative Specificity")

    @property
    def is_priority(self) -> Literal[True]:
        return True

    @property
    def bound_field(self) -> BoundField:
        return _field(self.field)

    @property
    def value_annotation(self) -> object:
        bound = self.bound_field
        return bound.model.model_fields[bound.field].rebuild_annotation()
