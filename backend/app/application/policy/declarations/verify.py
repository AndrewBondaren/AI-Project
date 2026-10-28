"""Verify explicit policy source types and reflect typed field bindings (tz_policy §4)."""

from dataclasses import dataclass
from enum import Enum
from inspect import get_annotations
from operator import attrgetter
from types import UnionType
from typing import Annotated, Generic, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.cascade.cascadeGraph import BoundField
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyDescriptor
from app.dataModel.policy.declarations.policyIdentity import PolicyScalar
from app.dataModel.policy.objectAdmissionPolicyDefinition import EnabledGate, EnabledGateDeclaration, ObjectAdmissionFacts
from app.dataModel.policy.policyReferences import DirectValueRef, FactValueRef, PolicyReference, PolicyValueRef, _fact_value_type, _is_fact_annotation, _plain
from app.dataModel.policy.policyRules import SelectPriorityDefaultEffect

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


@dataclass(frozen=True)
class AttachedSelection(Generic[B, R]):
    field: BoundField
    reference: PolicyValueRef[BaseModel, PolicyScalar]
    cases: tuple[ValueCase[PolicyScalar, B, R], ...]


@dataclass(frozen=True)
class VerifiedPolicy(Generic[B, R]):
    gates: tuple[EnabledGateDeclaration, ...]
    selections: tuple[AttachedSelection[B, R], ...]


def _enum(value: object, expected: type[B]) -> B:
    if not isinstance(value, expected) or type(value) is not expected:
        raise ValueError("foreign policy enum")
    return value


def _scalar(annotation: object) -> bool:
    annotation = _plain(annotation)
    if get_origin(annotation) in (Union, UnionType):
        return all(_scalar(member) for member in get_args(annotation))
    return (annotation is type(None) or isinstance(annotation, type)
            and issubclass(annotation, (Enum, bool, int, float, str)))


def _origin(model: type[BaseModel], name: str) -> type:
    return next((base for base in model.__mro__ if name in get_annotations(base)), model)


def _metadata(annotation: object) -> tuple[object, ...]:
    annotation = unwrap_wire_type(annotation)
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return _metadata(args[0]) + args[1:]
    return ()


def _gate(bound: BoundField) -> EnabledGate[BaseModel]:
    return EnabledGate(DirectValueRef[BaseModel, bool](FieldRef(lambda: bound.model, attrgetter(bound.field))))


def _check_ref(ref: PolicyReference, models: tuple[type[BaseModel], ...], *, admission: bool) -> None:
    model = ref.bound_field.model
    if model is ObjectAdmissionFacts:
        if not admission:
            raise ValueError("value policy cannot reference computed placement priority")
    elif model not in models:
        raise ValueError("policy reference requires explicit source model")


def _selection(policy: PolicyDescriptor[B, R], bound: BoundField,
               meta: SelectByValue[PolicyScalar, Enum, Enum]) -> AttachedSelection[B, R]:
    annotation = unwrap_wire_type(bound.model.model_fields[bound.field].rebuild_annotation())
    fact = _is_fact_annotation(annotation)
    value_type = _fact_value_type(annotation) if fact else annotation
    if not _scalar(value_type):
        raise ValueError("SelectByValue requires scalar or FactValue[scalar] field")
    # Reflection supplies exactly the verified field name; no source instance is read.
    reference: PolicyValueRef[BaseModel, PolicyScalar]
    if fact:
        reference = FactValueRef[BaseModel, PolicyScalar](FieldRef(lambda: bound.model, attrgetter(bound.field)))
    else:
        reference = DirectValueRef[BaseModel, PolicyScalar](FieldRef(lambda: bound.model, attrgetter(bound.field)))
    cases: list[ValueCase[PolicyScalar, B, R]] = []
    for case in meta.cases:
        try:
            TypeAdapter[object](value_type).validate_python(case.when, strict=True)
        except ValidationError as exc:
            raise ValueError("value case does not match attached field type") from exc
        cases.append(ValueCase(when=case.when, behavior=_enum(case.behavior, policy.behavior_type),
            reason=_enum(case.reason, policy.reason_type) if case.reason is not None else None,
            precedence=case.precedence))
    return AttachedSelection(bound, reference, tuple(cases))


def verify_policy(policy: PolicyDescriptor[B, R], models: tuple[type[BaseModel], ...]) -> VerifiedPolicy[B, R]:
    policy.__post_init__()
    if not isinstance(models, tuple) or any(not isinstance(m, type) or not issubclass(m, BaseModel) for m in models):
        raise ValueError("policy compilation requires explicit immutable model types")
    if len(set(models)) != len(models):
        raise ValueError("duplicate policy source model")
    gates: list[EnabledGateDeclaration] = []
    selections: list[AttachedSelection[B, R]] = []
    seen: set[tuple[type, str, type]] = set()
    for model in models:
        config = model.model_config
        if not config.get("frozen") or config.get("extra") != "forbid" or config.get("revalidate_instances") != "always":
            raise ValueError("policy source requires frozen, extra-forbid, revalidated POJO")
        for name, info in model.model_fields.items():
            for meta in tuple(info.metadata) + _metadata(info.annotation):
                if not isinstance(meta, (EnabledFor, SelectByValue)):
                    continue
                if meta.policy.owner is policy.owner and meta.policy is not policy:
                    raise ValueError("multiple policy descriptors share owner")
                if meta.policy is not policy:
                    continue
                meta.__post_init__()
                key = (_origin(model, name), name, type(meta))
                if key in seen:
                    raise ValueError("duplicate or ambiguous inherited policy field")
                seen.add(key)
                bound = BoundField(model, name)
                if isinstance(meta, EnabledFor):
                    annotation = info.rebuild_annotation()
                    if _plain(annotation) is not bool:
                        raise ValueError("enabled annotation requires non-nullable bool field")
                    adapter = TypeAdapter[object](annotation, config=ConfigDict(strict=bool(config.get("strict"))))
                    try:
                        adapter.validate_python(1)
                    except ValidationError:
                        pass
                    else:
                        raise ValueError("enabled annotation requires declared strict bool")
                    gates.append(_gate(bound))
                else:
                    selections.append(_selection(policy, bound, meta))
    admission = isinstance(policy, AdmissionPolicy)
    for case in policy.cases:
        case.__post_init__()
        for predicate in case.conditions:
            _check_ref(predicate.reference, models, admission=admission)
        if isinstance(case.effect, SelectPriorityDefaultEffect):
            _check_ref(case.effect.ref, models, admission=admission)
    if isinstance(policy, AdmissionPolicy):
        for ref in (policy.authored_priority_ref, policy.domain_priority_ref, policy.terminal_priority_ref):
            _check_ref(ref, models, admission=admission)
    return VerifiedPolicy(tuple(gates), tuple(selections))
