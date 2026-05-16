import json

from app.application.llm.models import ValidationResult
from app.application.engine.validation.validationStatus import ValidationStatus


class ContractValidator:

    def validate(self, output, contract) -> ValidationResult:

        if isinstance(output, str):
            try:
                output = json.loads(output)
            except Exception as e:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason=f"invalid_json: {str(e)}"
                )

        try:
            contract.model_validate(output)
        except Exception as e:
            return ValidationResult(
                status=ValidationStatus.RETRY,
                reason=f"schema_mismatch: {str(e)}"
            )

        return ValidationResult(status=ValidationStatus.OK)