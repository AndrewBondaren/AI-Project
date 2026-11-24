"""Preserve core facts through Pydantic's ValueError transport."""
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class PatchSetCoreInvariantError(ValueError):
    def __init__(self, violations: tuple[PatchSetInvariantViolation, ...]) -> None:
        collector = ValidatorAggregationHelper((PatchSetInvariantViolation,))
        for violation in violations:
            collector.add(violation)
        self.violations = collector.snapshot()
        if not self.violations:
            raise ValueError("core failure requires violations")
        super().__init__("PatchSet core invariants failed")
