"""Declared causes that policy transports from observation to decision."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import PolicyIssueReason, PolicyRuleId, PolicyStage
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PolicyTypeError(FieldPathError[PolicyIssueReason]):
    pass


class PolicyOperationIssue(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")
    message: str


class PolicyRuleIssue(PolicyOperationIssue, frozen=True):
    code: Literal[PolicyIssueReason.RULE_CONFLICT, PolicyIssueReason.RULE_NO_MATCH]
    stage: PolicyStage
    rule_ids: tuple[PolicyRuleId, ...]


type SupportFailureReason = Literal[PolicyIssueReason.MISSING_SUPPORT, PolicyIssueReason.FAILED_SUPPORT,
                                 PolicyIssueReason.DEPENDENCY_CYCLE]


class PolicySupportIssue(PolicyOperationIssue, frozen=True):
    code: SupportFailureReason | Literal[PolicyIssueReason.INVALID_INPUT]
    support_uid: EntityUid


class PolicyModelIssue(PolicyOperationIssue, frozen=True):
    code: Literal[PolicyIssueReason.INVALID_INPUT] = PolicyIssueReason.INVALID_INPUT
    model: ModelIdentity


type PolicyCause = PolicyModelIssue | PolicyRuleIssue | PolicySupportIssue | SerializeAsAny[FieldPathError[Any]]
