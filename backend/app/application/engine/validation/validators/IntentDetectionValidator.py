from app.application.engine.validation.validationStatus import ValidationResult, ValidationResult, ValidationStatus

#TODO Mock class for first pass
class IntentDetectionValidator:
    def validate(self, node, output, state) -> ValidationResult:
        return ValidationResult(status=ValidationStatus.OK)