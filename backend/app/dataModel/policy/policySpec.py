"""Typed in-process rule declarations; no matching, priority selection or IO."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import (
    Annotated, Generic, Literal, Protocol, TypeAlias, TypeVar, Union, get_args, get_origin,
)

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator
from typing_extensions import TypeAliasType

from app.dataModel.cascade.cascadeGraph import BoundField, bind_field
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.policyEnums import (
    FactState, PolicyDisableReason, PolicyIssueReason, PolicyOperation,
    PolicyRuleId, PolicyStage, RulePrecedence,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)

_RULE_ID = TypeAdapter(Annotated[PolicyRuleId, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")])
_PRECEDENCE = TypeAdapter(Annotated[RulePrecedence, Field(strict=True, ge=0)])
_UIDS = TypeAdapter(tuple[EntityUid, ...])


def _policy_value(value: object) -> None:
    """Facts and predicate values cannot hide mutable data in a frozen record."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and isfinite(value):
        return
    if isinstance(value, Enum):
        _policy_value(value.value)
        return
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            _policy_value(item)
        return
    if isinstance(value, BaseModel) and value.model_config.get("frozen"):
        if value.model_config.get("extra") != "forbid" or value.model_config.get("revalidate_instances") != "always":
            raise ValueError("policy value model requires immutable contract")
        for name in type(value).model_fields:
            _policy_value(getattr(value, name))
        return
    raise ValueError("policy values require immutable finite data")


class KnownFact(BaseModel, Generic[T_co], frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.KNOWN] = FactState.KNOWN
    value: T_co

    @model_validator(mode="after")
    def immutable_value(self):
        _policy_value(self.value)
        return self


class WaitingFact(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.WAITING] = FactState.WAITING
    support_uids: tuple[EntityUid, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_supports(self):
        if len(set(self.support_uids)) != len(self.support_uids):
            raise ValueError("duplicate waiting supports")
        return self


class UnknownFact(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.UNKNOWN] = FactState.UNKNOWN
    issue: FieldPathError


type FactValue[T] = Annotated[KnownFact[T] | WaitingFact | UnknownFact, Field(discriminator="state")]


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


class PolicyPredicate(Protocol):
    @property
    def reference(self) -> PolicyReference: ...


def _expected(reference: PolicyReference, value: object) -> None:
    if not isinstance(reference, (DirectValueRef, FactValueRef)):
        raise ValueError("predicate requires direct/fact reference")
    TypeAdapter[object](reference.value_annotation).validate_python(value, strict=True)
    _policy_value(value)


@dataclass(frozen=True)
class Equal(Generic[M, T]):
    reference: PolicyValueRef[M, T]
    expected: T

    def __post_init__(self) -> None:
        _expected(self.reference, self.expected)


@dataclass(frozen=True)
class InSet(Generic[M, T]):
    reference: PolicyValueRef[M, T]
    values: frozenset[T]

    def __post_init__(self) -> None:
        if not isinstance(self.values, frozenset) or not self.values:
            raise ValueError("InSet requires nonempty frozen values")
        for value in self.values:
            _expected(self.reference, value)


@dataclass(frozen=True)
class IsPresent(Generic[M, T]):
    reference: PolicyValueRef[M, T]

    def __post_init__(self) -> None:
        if not isinstance(self.reference, (DirectValueRef, FactValueRef)):
            raise ValueError("predicate requires direct/fact reference")


@dataclass(frozen=True)
class DisableEffect:
    reason: PolicyDisableReason

    def __post_init__(self) -> None:
        if not isinstance(self.reason, PolicyDisableReason):
            raise ValueError("disable effect requires common reason enum")


class PriorityDefaultSelection(Protocol):
    @property
    def ref(self) -> PriorityReference: ...


@dataclass(frozen=True)
class SelectPriorityDefaultEffect(Generic[M]):
    ref: PriorityValueRef[M]

    def __post_init__(self) -> None:
        if not isinstance(self.ref, PriorityValueRef):
            raise ValueError("priority default requires typed priority reference")


@dataclass(frozen=True)
class RequireSupportEffect:
    support_uids: tuple[EntityUid, ...]

    def __post_init__(self) -> None:
        _UIDS.validate_python(self.support_uids, strict=True)
        if not self.support_uids or len(set(self.support_uids)) != len(self.support_uids):
            raise ValueError("support effect requires unique nonempty UIDs")


@dataclass(frozen=True)
class SelectBehaviorEffect(Generic[B]):
    value: B

    def __post_init__(self) -> None:
        if not isinstance(self.value, Enum):
            raise ValueError("behavior effect requires domain enum")


@dataclass(frozen=True)
class PolicyRule(Generic[B, R]):
    id: PolicyRuleId
    stage: PolicyStage
    precedence: RulePrecedence
    conditions: tuple[PolicyPredicate, ...]
    effect: DisableEffect | PriorityDefaultSelection | RequireSupportEffect | SelectBehaviorEffect[B]
    domain_reason: R | None = None

    def __post_init__(self) -> None:
        _RULE_ID.validate_python(self.id, strict=True)
        _PRECEDENCE.validate_python(self.precedence, strict=True)
        if not isinstance(self.stage, PolicyStage) or not isinstance(self.conditions, tuple):
            raise ValueError("rule requires stage enum and tuple conditions")
        if any(not isinstance(condition, (Equal, InSet, IsPresent)) for condition in self.conditions):
            raise ValueError("rule conditions require declared predicates")
        if self.domain_reason is not None and not isinstance(self.domain_reason, Enum):
            raise ValueError("domain reason requires enum")
        stages = ((DisableEffect, tuple(PolicyStage)),
                  (SelectPriorityDefaultEffect, (PolicyStage.PRIORITY,)),
                  (RequireSupportEffect, (PolicyStage.SUPPORT,)),
                  (SelectBehaviorEffect, (PolicyStage.BEHAVIOR,)))
        if not any(isinstance(self.effect, kind) and self.stage in allowed for kind, allowed in stages):
            raise ValueError("effect is not permitted in this policy stage")


@dataclass(frozen=True)
class PolicyFallback(Generic[B]):
    reason: PolicyIssueReason
    behavior: B | None
    disable_object: bool

    def __post_init__(self) -> None:
        if not isinstance(self.reason, PolicyIssueReason) or type(self.disable_object) is not bool:
            raise ValueError("fallback requires reason enum and strict bool")
        if self.behavior is not None and not isinstance(self.behavior, Enum):
            raise ValueError("fallback behavior requires domain enum")


def _spec(rules: tuple[PolicyRule[B, R], ...], fallbacks: tuple[PolicyFallback[B], ...], behavior: type[B]) -> None:
    if not isinstance(behavior, type) or not issubclass(behavior, Enum):
        raise ValueError("spec requires behavior enum type")
    if not isinstance(rules, tuple) or not isinstance(fallbacks, tuple):
        raise ValueError("spec rules/fallbacks require tuples")
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("duplicate policy rule id")
    if len({fallback.reason for fallback in fallbacks}) != len(fallbacks):
        raise ValueError("duplicate fallback reason")
    if len({type(rule.domain_reason) for rule in rules if rule.domain_reason is not None}) > 1:
        raise ValueError("mixed domain reason enums")
    for rule in rules:
        if isinstance(rule.effect, SelectBehaviorEffect) and type(rule.effect.value) is not behavior:
            raise ValueError("foreign behavior enum in rule")
    for fallback in fallbacks:
        if fallback.behavior is not None and type(fallback.behavior) is not behavior:
            raise ValueError("foreign behavior enum in fallback")


@dataclass(frozen=True)
class ObjectAdmissionPolicySpec(Generic[B, R]):
    operation: Literal[PolicyOperation.OBJECT_ADMISSION]
    rules: tuple[PolicyRule[B, R], ...]
    authored_priority_ref: PriorityReference
    domain_priority_ref: PriorityReference
    terminal_priority_ref: PriorityReference
    expected_behavior_type: type[B]
    fallback_rules: tuple[PolicyFallback[B], ...]

    def __post_init__(self) -> None:
        if self.operation is not PolicyOperation.OBJECT_ADMISSION:
            raise ValueError("object admission spec cannot become value selection")
        for ref in (self.authored_priority_ref, self.domain_priority_ref, self.terminal_priority_ref):
            if not isinstance(ref, PriorityValueRef):
                raise ValueError("admission requires typed priority refs")
        _spec(self.rules, self.fallback_rules, self.expected_behavior_type)


@dataclass(frozen=True)
class ValueSelectionPolicySpec(Generic[B, R]):
    operation: Literal[PolicyOperation.VALUE_SELECTION]
    rules: tuple[PolicyRule[B, R], ...]
    expected_behavior_type: type[B]
    fallback_rules: tuple[PolicyFallback[B], ...]

    def __post_init__(self) -> None:
        if self.operation is not PolicyOperation.VALUE_SELECTION:
            raise ValueError("value selection requires its operation tag")
        if any(rule.stage is PolicyStage.PRIORITY for rule in self.rules):
            raise ValueError("value selection has no priority stage")
        _spec(self.rules, self.fallback_rules, self.expected_behavior_type)


PolicySpec: TypeAlias = Union[ObjectAdmissionPolicySpec[B, R], ValueSelectionPolicySpec[B, R]]
