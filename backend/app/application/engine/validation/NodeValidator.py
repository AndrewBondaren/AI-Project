from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class NodeValidator:

    def validate(self, node, output, state) -> ValidationResult:
        if node.validator is None:
            return ValidationResult(status=ValidationStatus.OK)

        return node.validator().validate(node, output, state)