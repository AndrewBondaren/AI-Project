"""Frozen policy results. A decision carries facts, never a resolver callback."""

from enum import Enum
from typing import Annotated, Generic, Literal, Self
from typing_extensions import TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, StringConstraints, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.policyEnums import (
    PolicyDisableReason, PolicyOperation, PolicyOrigin, PolicyRuleId, PolicyState,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


B_co = TypeVar("B_co", bound=Enum, covariant=True)
R_co = TypeVar("R_co", bound=Enum, covariant=True)
Op_co = TypeVar("Op_co", bound=PolicyOperation, covariant=True, default=PolicyOperation)


class PolicyReason(BaseModel, Generic[R_co], frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    domain_reason: R_co | None
    common_reason: PolicyDisableReason


class PolicyProvenance(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    origin: PolicyOrigin
    source_path: tuple[StrictStr | StrictInt, ...]
    rule_id: Annotated[PolicyRuleId | None, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")]

    @model_validator(mode="after")
    def rule_identity(self) -> Self:
        if self.origin is PolicyOrigin.RULE and self.rule_id is None:
            raise ValueError("rule provenance requires rule_id")
        return self


class PolicyDecision(BaseModel, Generic[B_co, R_co, Op_co], frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    operation: Op_co
    state: PolicyState
    effective_priority: Specificity | None
    behavior: B_co | None
    reasons: tuple[PolicyReason[R_co], ...]
    waiting_supports: tuple[EntityUid, ...]
    provenance: tuple[PolicyProvenance, ...]
    issues: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        if len(set(self.waiting_supports)) != len(self.waiting_supports):
            raise ValueError("duplicate waiting supports")
        if self.state is PolicyState.WAITING_SUPPORT and not self.waiting_supports:
            raise ValueError("waiting decision requires supports")
        if self.state is PolicyState.UNRESOLVED and not self.issues:
            raise ValueError("unresolved decision requires issues")
        if self.state is PolicyState.READY:
            if self.issues or self.waiting_supports:
                raise ValueError("ready decision cannot retain unresolved inputs")
            if self.operation is PolicyOperation.OBJECT_ADMISSION:
                if self.effective_priority is None or self.effective_priority <= 0:
                    raise ValueError("ready admission requires positive priority")
            elif self.behavior is None:
                raise ValueError("ready value selection requires behavior")
        if self.operation is PolicyOperation.VALUE_SELECTION and self.effective_priority is not None:
            raise ValueError("value selection has no placement priority")
        return self

    def require_behavior(self) -> B_co:
        if self.behavior is None:
            raise ValueError("policy decision has no selected behavior")
        return self.behavior


class ObjectAdmissionDecision(PolicyDecision[B_co, R_co, Literal[PolicyOperation.OBJECT_ADMISSION]], frozen=True):
    pass


class ValueSelectionDecision(PolicyDecision[B_co, R_co, Literal[PolicyOperation.VALUE_SELECTION]], frozen=True):
    pass
