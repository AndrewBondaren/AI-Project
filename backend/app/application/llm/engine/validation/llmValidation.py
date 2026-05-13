import json
from app.application.llm.engine.validation.validationStatus import ValidationResult, ValidationStatus

class LLMValidator:

    def validate(self, response, state) -> ValidationResult:

        if not response:
            return ValidationResult(status=ValidationStatus.RETRY, reason="empty")

        try:
            data = json.loads(response)
        except Exception:
            return ValidationResult(status=ValidationStatus.RETRY, reason="invalid_json")

        if "type" not in data:
            return ValidationResult(status=ValidationStatus.RETRY, reason="missing_type")

        return ValidationResult(status=ValidationStatus.OK)