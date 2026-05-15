import json
from dataclasses import is_dataclass
from pydantic import BaseModel
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class ContractValidator:

    def validate(self, output, contract) -> ValidationResult:

        # -----------------------
        # 1. normalize
        # -----------------------
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except Exception as e:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason=f"invalid_json: {str(e)}"
                )

        # -----------------------
        # 2. schema check
        # -----------------------
        schema = getattr(contract, "output_schema", None)

        if schema:

            try:
                if issubclass(schema, BaseModel):
                    schema.model_validate(output)

                elif is_dataclass(schema):
                    schema(**output)

                elif isinstance(schema, dict):
                    # future: jsonschema support
                    pass

            except Exception as e:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason=f"schema_mismatch: {str(e)}"
                )

        # -----------------------
        # 3. required fields
        # -----------------------
        required = getattr(contract, "required_fields", None)

        if required:
            for field in required:
                if field not in output:
                    return ValidationResult(
                        status=ValidationStatus.RETRY,
                        reason=f"missing_field: {field}"
                    )

        return ValidationResult(status=ValidationStatus.OK)