"""Closed policy vocabulary, independent of water, terrain and execution mode."""

from enum import StrEnum
from typing import NewType


PolicyRuleId = NewType("PolicyRuleId", str)
RulePrecedence = NewType("RulePrecedence", int)


class PolicyStage(StrEnum):
    ABSOLUTE_GATE = "absolute_gate"
    PRIORITY = "priority"
    SUPPORT = "support"
    BEHAVIOR = "behavior"


class FactState(StrEnum):
    KNOWN = "known"
    WAITING = "waiting"
    UNKNOWN = "unknown"


class PolicyOperation(StrEnum):
    OBJECT_ADMISSION = "object_admission"
    VALUE_SELECTION = "value_selection"


class PolicyState(StrEnum):
    READY = "ready"
    DISABLED = "disabled"
    WAITING_SUPPORT = "waiting_support"
    UNRESOLVED = "unresolved"


class PolicyOrigin(StrEnum):
    AUTHORED = "authored"
    DOMAIN_DEFAULT = "domain_default"
    TERMINAL_DEFAULT = "terminal_default"
    RULE = "rule"
    FALLBACK = "fallback"


class PolicyDisableReason(StrEnum):
    ENABLED_FALSE = "enabled_false"
    ZERO_PRIORITY = "zero_priority"
    POLICY_FORBID = "policy_forbid"
    SUPPORT_DISABLED = "support_disabled"
    ERROR_FALLBACK = "error_fallback"
    DOMAIN_RULE = "domain_rule"


class PolicyIssueReason(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNKNOWN_FACT = "unknown_fact"
    RULE_CONFLICT = "rule_conflict"
    MISSING_SUPPORT = "missing_support"
    FAILED_SUPPORT = "failed_support"
    DEPENDENCY_CYCLE = "dependency_cycle"
    RULE_NO_MATCH = "rule_no_match"
