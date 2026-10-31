# TODO(B2/B2-L19): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.validation.nodeValidator.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext


class NodeValidator:

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:
        if ctx.node.validator is None:
            return ValidationResult(status=ValidationStatus.OK)

        return ctx.node.validator().validate(ctx)
