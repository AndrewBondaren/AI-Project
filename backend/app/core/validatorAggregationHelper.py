"""Collect field diagnostics for one validation stage."""

from collections.abc import Callable

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ValidatorAggregationHelper:
    def __init__(self) -> None:
        self._issues: list[FieldPathError] = []

    def add(self, issue: FieldPathError) -> None:
        self._issues.append(issue)

    def raise_if_any(self, failure: Callable[[tuple[FieldPathError, ...]], Exception]) -> None:
        if self._issues:
            raise failure(tuple(self._issues))
