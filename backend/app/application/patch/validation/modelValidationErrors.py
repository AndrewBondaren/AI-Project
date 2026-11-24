"""Classify root request errors without losing locations or relation facts."""
from pydantic import ValidationError
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.application.patch.errors import PatchSetValidationClassificationError
from app.dataModel.patch.validation.coreInvariantError import PatchSetCoreInvariantError
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.validation.admissionReasons import PatchSetStructuralFailure
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class PatchSetModelValidationErrors:
    @classmethod
    def classify(cls, error: ValidationError) -> tuple[PatchSetStructuralFailure | PatchSetInvariantViolation, ...]:
        collector = ValidatorAggregationHelper[PatchSetStructuralFailure | PatchSetInvariantViolation](
            (PatchSetStructuralFailure, PatchSetInvariantViolation))
        for entry in error.errors(include_url=False, include_input=False):
            error_type = entry["type"]
            cause = (entry.get("ctx") or {}).get("error")
            if type(cause) is PatchSetCoreInvariantError and entry["loc"] == ():
                for violation in cause.violations:
                    collector.add(violation)
            elif "error" not in (entry.get("ctx") or {}):
                try:
                    kind = PatchSetStructuralErrorKind(error_type)
                except ValueError:
                    raise PatchSetValidationClassificationError("unclassified structural error code") from error
                if any(type(part) not in (str, int) for part in entry["loc"]):
                    raise PatchSetValidationClassificationError("unsupported validation location") from error
                collector.add(PatchSetStructuralFailure(error_type=kind,
                    loc=entry["loc"], message=entry["msg"]))
            else:
                raise PatchSetValidationClassificationError("unclassified model validation failure") from error
        return collector.snapshot()
