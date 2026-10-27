"""Stage matching, precedence and required-support observations."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from app.application.policy.policyRead import ConditionResult, PolicyReader, issue
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import PolicyIssueReason, PolicyStage, PolicySupportState
from app.dataModel.policy.policyRules import (
    DisableEffect, PolicyRule, RequireSupportEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


@dataclass(frozen=True)
class PolicyProblem:
    reason: PolicyIssueReason
    issues: tuple[FieldPathError, ...]


@dataclass(frozen=True)
class StageResult(Generic[B, R]):
    matched: tuple[PolicyRule[B, R], ...] = ()
    waiting: tuple[EntityUid, ...] = ()
    problems: tuple[PolicyProblem, ...] = ()
    disabled_supports: tuple[EntityUid, ...] = ()


def evaluate_stage(rules: tuple[PolicyRule[B, R], ...], stage: PolicyStage,
                   reader: PolicyReader) -> StageResult[B, R]:
    ordered = sorted((r for r in rules if r.stage is stage), key=lambda r: (-r.precedence, r.id))
    matches: list[PolicyRule[B, R]] = []
    pending: list[tuple[PolicyRule[B, R], ConditionResult]] = []
    for rule in ordered:
        value = reader.conditions(rule.conditions)
        if value.matches is True:
            matches.append(rule)
        elif value.matches is None:
            pending.append((rule, value))
    if any(isinstance(rule.effect, DisableEffect) for rule in matches):
        return StageResult(matched=tuple(matches))
    selections = [r for r in matches if isinstance(r.effect, (SelectBehaviorEffect, SelectPriorityDefaultEffect))]
    highest = max((r.precedence for r in selections), default=-1)
    problems: list[PolicyProblem] = []
    waiting: set[EntityUid] = set()
    for rule, value in pending:
        if isinstance(rule.effect, (SelectBehaviorEffect, SelectPriorityDefaultEffect)) and rule.precedence < highest:
            continue
        if value.issues:
            problems.append(PolicyProblem(PolicyIssueReason.UNKNOWN_FACT, value.issues))
        else:
            waiting.update(value.waiting)
    disabled: set[EntityUid] = set()
    observations = {s.uid: s for s in reader.facts.supports}
    for rule in matches:
        if not isinstance(rule.effect, RequireSupportEffect):
            continue
        for uid in rule.effect.support_uids:
            support = observations.get(uid)
            state = support.state if support else PolicySupportState.MISSING
            if state is PolicySupportState.PENDING:
                waiting.add(uid)
            elif state is PolicySupportState.DISABLED:
                disabled.add(uid)
            elif state is not PolicySupportState.ACCEPTED:
                reason = {PolicySupportState.MISSING: PolicyIssueReason.MISSING_SUPPORT,
                          PolicySupportState.FAILED: PolicyIssueReason.FAILED_SUPPORT,
                          PolicySupportState.CYCLE: PolicyIssueReason.DEPENDENCY_CYCLE}[state]
                details = support.issues if support and support.issues else (
                    issue(reason, ("supports", uid), f"required support is {state.value}"),)
                problems.append(PolicyProblem(reason, details))
    return StageResult(tuple(matches), tuple(sorted(waiting)), tuple(problems), tuple(sorted(disabled)))


def selection_rules(result: StageResult[B, R]) -> tuple[PolicyRule[B, R], ...]:
    choices = tuple(r for r in result.matched if isinstance(r.effect, (SelectBehaviorEffect, SelectPriorityDefaultEffect)))
    highest = max((r.precedence for r in choices), default=-1)
    return tuple(r for r in choices if r.precedence == highest)
