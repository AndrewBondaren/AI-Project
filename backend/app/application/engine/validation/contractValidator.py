# TODO(B2/B2-L18): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.validation.contractValidator.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

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
