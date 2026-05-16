from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity


class IntentDetectionValidator:

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:

        errors = []

        # assert 1
        if not ctx.output.get("intent"):
            errors.append(NodeValidationError(
                code="missing_intent",
                message="Field 'intent' is missing or empty",
                severity=NodeErrorSeverity.RETRY,
                field="intent",
            ))

        # assert 2
        confidence = ctx.output.get("confidence", 0)
        if confidence < 0.5:
            errors.append(NodeValidationError(
                code="low_confidence",
                message=f"Confidence {confidence} is below threshold 0.5",
                severity=NodeErrorSeverity.RETRY,
                field="confidence",
            ))

        if not errors:
            return ValidationResult(status=ValidationStatus.OK)

        # severity: если хоть одна FAIL — весь результат FAIL
        status = (
            ValidationStatus.FAIL
            if any(e.severity == NodeErrorSeverity.FAIL for e in errors)
            else ValidationStatus.RETRY
        )

        return ValidationResult(status=status, errors=errors)