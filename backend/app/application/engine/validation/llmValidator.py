from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class LLMValidator:

    def __init__(self, contract_validator, node_validator):
        self.contract_validator = contract_validator
        self.node_validator = node_validator

    def validate(self, node, output, state) -> ValidationResult:

        # 1. JSON структура — только если есть contract_json
        if node.contract_json:
            result = self.contract_validator.validate(
                output=output,
                contract=node.contract_json
            )
            if not result.ok:
                return result

        # 2. бизнес логика — только если есть validator
        if node.validator:
            return self.node_validator.validate(
                node=node,
                output=output,
                state=state
            )

        return ValidationResult(status=ValidationStatus.OK)