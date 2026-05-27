from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity


class ContextSnapGathererValidator:

    def validate(self, ctx: NodeValidationContext) -> ValidationResult:
        errors = []
        output = ctx.output

        for field in ("location", "situation", "player_state"):
            if not output.get(field):
                errors.append(NodeValidationError(
                    code=f"missing_{field}",
                    message=f"'{field}' is empty or missing",
                    severity=NodeErrorSeverity.RETRY,
                    field=field,
                ))

        actors = output.get("actors")
        if not isinstance(actors, list):
            errors.append(NodeValidationError(
                code="invalid_actors",
                message="'actors' must be a list",
                severity=NodeErrorSeverity.RETRY,
                field="actors",
            ))

        if not errors:
            return ValidationResult(status=ValidationStatus.OK)

        return ValidationResult(status=ValidationStatus.RETRY, errors=errors)
