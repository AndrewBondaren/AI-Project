import json

from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity


class ContractValidator:

    def validate(self, output, contract) -> ValidationResult:

        if isinstance(output, str):
            try:
                output = json.loads(output)
            except Exception as e:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    errors=[NodeValidationError(
                        code="invalid_json",
                        message=str(e),
                        severity=NodeErrorSeverity.RETRY,
                    )],
                )

        try:
            contract.model_validate(output)
        except Exception as e:
            return ValidationResult(
                status=ValidationStatus.RETRY,
                errors=[NodeValidationError(
                    code="schema_mismatch",
                    message=str(e),
                    severity=NodeErrorSeverity.RETRY,
                )],
            )

        return ValidationResult(status=ValidationStatus.OK)
