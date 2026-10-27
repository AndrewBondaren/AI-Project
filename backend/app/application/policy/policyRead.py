"""Read declared fields and evaluate AND predicates without domain callbacks."""

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.objectAdmissionPolicyDefinition import ObjectAdmissionFacts
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, SourcePath
from app.dataModel.policy.policyEnums import PolicyIssueReason
from app.dataModel.policy.policyFacts import FactValue, KnownFact, UnknownFact, WaitingFact
from app.dataModel.policy.policyReferences import FactValueRef, PolicyReference
from app.dataModel.policy.policyRules import Equal, InSet, IsPresent, PolicyPredicate
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def issue(reason: PolicyIssueReason, path: SourcePath, message: str) -> FieldPathError:
    return FieldPathError(path, message, code=reason.value)


@dataclass(frozen=True)
class ConditionResult:
    matches: bool | None
    waiting: tuple[EntityUid, ...] = ()
    issues: tuple[FieldPathError, ...] = ()


@dataclass(frozen=True)
class PolicyReader:
    sources: PolicyInputs
    facts: PolicyFacts
    computed: ObjectAdmissionFacts | None = None

    def validate(self) -> tuple[FieldPathError, ...]:
        models = self.sources.models + self.facts.models
        if len({m.model for m in models}) != len(models):
            raise ValueError("source/fact model binding is ambiguous")
        if any(m.model is ObjectAdmissionFacts for m in models):
            raise ValueError("effective priority is owned by the executor")
        errors: list[FieldPathError] = []
        for binding in models:
            try:
                binding.model.model_validate(binding.instance, strict=True)
            except ValidationError as exc:
                for error in exc.errors():
                    errors.append(issue(PolicyIssueReason.INVALID_INPUT, binding.path + error["loc"], error["msg"]))
        for support in self.facts.supports:
            try:
                type(support).model_validate(support, strict=True)
            except ValidationError as exc:
                errors.append(issue(PolicyIssueReason.INVALID_INPUT, ("supports", support.uid), str(exc)))
        return tuple(errors)

    def path(self, reference: PolicyReference) -> SourcePath:
        bound = reference.bound_field
        binding = next((m for m in self.sources.models + self.facts.models if m.model is bound.model), None)
        return (binding.path if binding else (bound.model.__name__,)) + (bound.field,)

    def read(self, reference: PolicyReference) -> FactValue[object]:
        bound = reference.bound_field
        if bound.model is ObjectAdmissionFacts:
            instance = self.computed
        else:
            binding = next((m for m in self.sources.models + self.facts.models if m.model is bound.model), None)
            instance = binding.instance if binding else None
        if instance is None:
            return UnknownFact(issue=issue(PolicyIssueReason.UNKNOWN_FACT, self.path(reference), "policy source is unavailable"))
        value: object = getattr(instance, bound.field)
        if isinstance(reference, FactValueRef):
            if isinstance(value, (KnownFact, WaitingFact, UnknownFact)):
                return value
            return UnknownFact(issue=issue(PolicyIssueReason.INVALID_INPUT, self.path(reference), "expected FactValue"))
        TypeAdapter[object](reference.value_annotation).validate_python(value, strict=True)
        return KnownFact[object](value=value)

    def conditions(self, predicates: tuple[PolicyPredicate, ...]) -> ConditionResult:
        unknowns: list[UnknownFact] = []
        supports: set[EntityUid] = set()
        false = False
        for predicate in predicates:
            value = self.read(predicate.reference)
            if isinstance(value, UnknownFact):
                unknowns.append(value)
            elif isinstance(value, WaitingFact):
                supports.update(value.support_uids)
            elif isinstance(predicate, Equal):
                false |= value.value != predicate.expected
            elif isinstance(predicate, InSet):
                false |= value.value not in predicate.values
            elif isinstance(predicate, IsPresent):
                false |= value.value is None
            else:
                raise ValueError("unsupported policy predicate")
        if false:
            return ConditionResult(matches=False)
        if unknowns:
            return ConditionResult(matches=None, issues=tuple(dict.fromkeys(u.issue for u in unknowns)))
        if supports:
            return ConditionResult(matches=None, waiting=tuple(sorted(supports)))
        return ConditionResult(matches=True)
