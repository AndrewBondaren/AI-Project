from app.application.engine.taskType import TaskType
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity

CONFIDENCE_THRESHOLD = 0.5


class IntentDetectionValidator:

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:

        if ctx.output.get("reasoning") == "gibberish":
            return ValidationResult(
                status=ValidationStatus.USER_ERROR,
                errors=[NodeValidationError(
                    code="gibberish",
                    message="Player message is not interpretable",
                    severity=NodeErrorSeverity.USER_ERROR,
                )]
            )

        errors = []
        valid_task_types = {t.value for t in TaskType if not t.is_technical}
        intents = ctx.output.get("intents", [])

        if not intents:
            return ValidationResult(
                status=ValidationStatus.RETRY,
                errors=[NodeValidationError(
                    code="missing_intent",
                    message="LLM returned empty intents list",
                    severity=NodeErrorSeverity.RETRY,
                    field="intents",
                )]
            )

        for idx, intent in enumerate(intents):
            task_type = intent.get("task_type")
            confidence = intent.get("confidence", 0)

            if task_type not in valid_task_types:
                errors.append(NodeValidationError(
                    code="invalid_task_type",
                    message=f"intents[{idx}].task_type='{task_type}' is not a valid TaskType",
                    severity=NodeErrorSeverity.RETRY,
                    field=f"intents[{idx}].task_type",
                ))

            if confidence < CONFIDENCE_THRESHOLD:
                errors.append(NodeValidationError(
                    code="low_confidence",
                    message=f"intents[{idx}].task_type='{task_type}' confidence={confidence} below threshold={CONFIDENCE_THRESHOLD}",
                    severity=NodeErrorSeverity.RETRY,
                    field=f"intents[{idx}].confidence",
                ))

        if not errors:
            return ValidationResult(status=ValidationStatus.OK)

        status = (
            ValidationStatus.FAIL
            if any(e.severity == NodeErrorSeverity.FAIL for e in errors)
            else ValidationStatus.RETRY
        )

        return ValidationResult(status=status, errors=errors)
