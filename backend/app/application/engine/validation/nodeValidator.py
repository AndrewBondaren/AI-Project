from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext


class NodeValidator:

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:
        if ctx.node.validator is None:
            return ValidationResult(status=ValidationStatus.OK)

        return ctx.node.validator().validate(ctx)
