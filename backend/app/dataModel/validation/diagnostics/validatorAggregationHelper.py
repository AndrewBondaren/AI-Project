"""Request-local collector of concrete issues for one validation stage.

Plan: ``.cursor/plans/error-contracts-1.md`` §3.9 C0-5. Admission is by
exact class, never by ``isinstance`` on a parameterized generic.
"""

from collections.abc import Callable
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.dataModel.validation.immutableValue import validate_immutable

IssueT = TypeVar("IssueT")


class IssueAdmissionError(ValueError):
    """Programming error: issue of a non-admitted class or a mutable issue."""


class ValidatorAggregationHelper(Generic[IssueT]):
    def __init__(self, admitted: tuple[type[IssueT], ...]) -> None:
        if not admitted or not all(isinstance(kind, type) for kind in admitted):
            raise IssueAdmissionError("collector needs at least one concrete issue class")
        for kind in admitted:
            if issubclass(kind, BaseModel) and not (
                    kind.model_config.get("frozen") and kind.model_config.get("revalidate_instances") == "always"):
                raise IssueAdmissionError(
                    f"{kind.__qualname__} must be frozen with revalidate_instances='always'")
        self._admitted = admitted
        self._issues: list[IssueT] = []

    def add(self, issue: IssueT) -> None:
        if type(issue) not in self._admitted:
            raise IssueAdmissionError(f"issue class {type(issue).__qualname__} is not admitted")
        try:
            if isinstance(issue, BaseModel):
                type(issue).model_validate(issue, strict=True)
            validate_immutable(issue)
        except (ValueError, ValidationError) as exc:
            raise IssueAdmissionError("issue must be a complete immutable record") from exc
        self._issues.append(issue)

    def snapshot(self) -> tuple[IssueT, ...]:
        return tuple(self._issues)

    def raise_if_any(self, failure: Callable[[tuple[IssueT, ...]], Exception]) -> None:
        if self._issues:
            raise failure(tuple(self._issues))
