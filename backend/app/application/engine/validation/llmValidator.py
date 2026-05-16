from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext


class LLMValidator:

    def __init__(self, contract_validator, node_validator):
        self.contract_validator = contract_validator
        self.node_validator = node_validator

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:

        # 1. структура contract_json
        if ctx.node.contract_json:
            result = self.contract_validator.validate(
                output=ctx.output,
                contract=ctx.node.contract_json,
            )
            if not result.ok:
                return result

        # 2. бизнес-логика
        if ctx.node.validator:
            return self.node_validator.validate(ctx)

        return ValidationResult(status=ValidationStatus.OK)