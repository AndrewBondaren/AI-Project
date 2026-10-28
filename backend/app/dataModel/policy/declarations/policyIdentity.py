"""Immutable addresses and the one deterministic rule ID encoding (tz_policy §3)."""

import json
from dataclasses import dataclass
from enum import Enum, StrEnum
from math import isfinite

from pydantic import BaseModel

from app.dataModel.cascade.cascadeGraph import BoundField
from app.dataModel.policy.declarations.policyDeclaration import PolicyOwner, validate_policy_owner
from app.dataModel.policy.policyFacts import _policy_value
from app.dataModel.policy.policyEnums import PolicyRuleId

type PolicyScalar = Enum | bool | int | float | str | None


class CommonPolicyOwner(PolicyOwner):
    """Owner for low-level common admission definitions without a domain descriptor."""


class RuleKind(StrEnum):
    ENABLED = "enabled"
    VALUE_CASE = "value_case"
    COMPOSITE_CASE = "composite_case"
    ZERO_PRIORITY = "zero_priority"


@dataclass(frozen=True, eq=False)
class ValueBranch:
    value: PolicyScalar

    def __post_init__(self) -> None:
        if isinstance(self.value, Enum):
            _policy_value(self.value)
            return
        if self.value is None or isinstance(self.value, (bool, int, str)):
            return
        if isinstance(self.value, float) and isfinite(self.value):
            return
        raise ValueError("value case requires finite scalar or enum")

    def _key(self) -> tuple[type, object]:
        value = self.value
        if isinstance(value, Enum):
            return type(value), value.name
        if isinstance(value, bool):
            return bool, value
        if isinstance(value, int):
            return int, value
        if isinstance(value, float):
            return float, value.hex()
        if isinstance(value, str):
            return str, value
        return type(None), None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ValueBranch) and self._key() == other._key()

    def __hash__(self) -> int:
        # Only for in-process duplicate detection, never for serialized rule IDs.
        return hash(self._key())


@dataclass(frozen=True, kw_only=True)
class RuleIdentity:
    owner: type[PolicyOwner]
    kind: RuleKind
    field: BoundField | None = None
    branch: ValueBranch | None = None
    case_key: Enum | None = None

    def __post_init__(self) -> None:
        validate_policy_owner(self.owner)
        if not isinstance(self.kind, RuleKind):
            raise ValueError("rule identity requires RuleKind")
        if self.field is not None:
            if (not isinstance(self.field, BoundField) or not isinstance(self.field.model, type)
                    or not issubclass(self.field.model, BaseModel) or self.field.field not in self.field.model.model_fields):
                raise ValueError("rule identity requires existing bound field")
        if self.branch is not None and not isinstance(self.branch, ValueBranch):
            raise ValueError("rule identity requires typed value branch")
        if self.case_key is not None and not isinstance(self.case_key, Enum):
            raise ValueError("rule identity requires enum case key")
        _policy_value(self.case_key)
        field_rule = self.kind in (RuleKind.ENABLED, RuleKind.VALUE_CASE)
        if (self.field is not None) is not field_rule:
            raise ValueError("field identity does not match rule kind")
        if (self.branch is not None) is not (self.kind is RuleKind.VALUE_CASE):
            raise ValueError("branch identity does not match rule kind")
        if (self.case_key is not None) is not (self.kind is RuleKind.COMPOSITE_CASE):
            raise ValueError("case key does not match rule kind")


def _enum_address(value: Enum) -> tuple[str, str, str]:
    return type(value).__module__, type(value).__qualname__, value.name


def _scalar_address(branch: ValueBranch) -> tuple[object, ...]:
    branch.__post_init__()
    value = branch.value
    if isinstance(value, Enum):
        return ("enum", *_enum_address(value))
    if isinstance(value, bool):
        return "bool", value
    if isinstance(value, int):
        return "int", value
    if isinstance(value, float):
        return "float", value.hex()
    if isinstance(value, str):
        return "str", value
    return ("null",)


def make_rule_id(identity: RuleIdentity) -> PolicyRuleId:
    """Encode declaration identity only; no outcome, precedence, or process hash."""
    if not isinstance(identity, RuleIdentity):
        raise ValueError("rule ID requires RuleIdentity")
    identity.__post_init__()
    field = identity.field
    parts = (
        (identity.owner.__module__, identity.owner.__qualname__), identity.kind.value,
        (field.model.__module__, field.model.__qualname__, field.field) if field is not None else None,
        _scalar_address(identity.branch) if identity.branch is not None else None,
        _enum_address(identity.case_key) if identity.case_key is not None else None,
    )
    return PolicyRuleId("policy-rule/v1:" + json.dumps(parts, ensure_ascii=True, separators=(",", ":"), allow_nan=False))
