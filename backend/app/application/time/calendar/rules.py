from dataclasses import dataclass

from app.dataModel.world.calendar.definitions.definition import CalendarDefinition
from app.dataModel.world.calendar.projection.request import CalendarBudget
from app.dataModel.world.calendar.rules.edits import CalendarSpan, InsertSpanRule, RemoveSpanRule
from app.dataModel.world.calendar.rules.predicates import Predicate, YearModuloPredicate, YearRangePredicate


class InvalidCalendar(ValueError):
    def __init__(self, path: tuple[str | int, ...], message: str):
        super().__init__(message)
        self.path = path


class ExhaustedBudget(Exception):
    pass


@dataclass
class Work:
    patterns: int
    checks: int

    @classmethod
    def from_budget(cls, budget: CalendarBudget) -> "Work":
        return cls(budget.max_year_patterns, budget.max_rule_checks)


def matches(predicate: Predicate, year: int) -> bool:
    if isinstance(predicate, YearModuloPredicate):
        return (year - predicate.offset) % predicate.modulus == predicate.residue
    if isinstance(predicate, YearRangePredicate):
        return predicate.first <= year <= predicate.last
    return True


def year_shape(definition: CalendarDefinition, year: int, work: Work) -> tuple[CalendarSpan, ...]:
    spans = list(definition.base_year)
    for index, rule in enumerate(definition.rules):
        work.checks -= 1
        if work.checks < 0:
            raise ExhaustedBudget
        if not all(matches(p, year) for p in rule.condition.all_of):
            continue
        if any(matches(p, year) for p in rule.condition.none_of):
            continue
        keys = [span.span for span in spans]
        path = ("rules", index)
        if isinstance(rule, InsertSpanRule):
            if rule.value.span in keys or (rule.after is not None and rule.after not in keys):
                raise InvalidCalendar(path, "invalid insert target")
            spans.insert(0 if rule.after is None else keys.index(rule.after) + 1, rule.value)
        elif isinstance(rule, RemoveSpanRule):
            if rule.span not in keys:
                raise InvalidCalendar(path, "missing remove target")
            spans.pop(keys.index(rule.span))
        else:
            if rule.value.span not in keys:
                raise InvalidCalendar(path, "missing replace target")
            spans[keys.index(rule.value.span)] = rule.value
    if not spans:
        raise InvalidCalendar(("rules",), "year must contain at least one day")
    return tuple(spans)
