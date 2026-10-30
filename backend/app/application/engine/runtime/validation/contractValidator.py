"""POJO boundary admission, reusing Pydantic schemas and immutableValue."""

from dataclasses import fields, is_dataclass
from typing import cast

from pydantic import BaseModel, RootModel, ValidationError

from app.application.engine.validation.nodeValidationError import NodeErrorSeverity, NodeValidationError
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.engine.dag.errors.nodeError import NodeError


def _declared_instance[T: BaseModel](value: object, contract: type[T]) -> T:
    if not isinstance(value, contract):
        raise ValueError(f"ready POJO must be an instance of {contract.__name__}")
    return value


def _model_source(value: BaseModel) -> object:
    if isinstance(value, RootModel):
        return cast(RootModel[object], value).root
    return vars(value)


def _check_existing_models(value: BaseModel) -> None:
    # Pydantic's default revalidate_instances='never' trusts existing nested
    # models. Validate each concrete model from its field references instead;
    # never serialize/deepcopy the payload or replace the admitted instances.
    pending: list[object] = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, BaseModel):
            checked = type(item).model_validate(_model_source(item), strict=True, by_name=True)
            if checked != item:
                raise ValueError("ready POJO must already satisfy its canonical contract")
            pending.extend(vars(item).values())
            pending.extend((item.__pydantic_private__ or {}).values())
        elif isinstance(item, (tuple, frozenset)):
            pending.extend(cast(tuple[object, ...] | frozenset[object], item))
        elif is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, field.name) for field in fields(item))


def _failure(error: ValueError | TypeError, *, retry: bool) -> ValidationResult:
    severity = NodeErrorSeverity.RETRY if retry else NodeErrorSeverity.FAIL
    status = ValidationStatus.RETRY if retry else ValidationStatus.FAIL
    if isinstance(error, ValidationError):
        errors = [
            NodeValidationError(
                code="invalid_json" if issue["type"] == "json_invalid" else "schema_mismatch",
                message=issue["msg"], severity=severity,
                field=".".join(str(part) for part in issue["loc"]) or None,
            )
            for issue in error.errors(include_input=False, include_context=False, include_url=False)
        ]
    else:
        errors = [NodeValidationError(code="schema_mismatch", message=str(error), severity=severity)]
    return ValidationResult(status=status, errors=errors)


class ContractValidator:
    def validate_error[E: NodeError](
        self, value: object, error_types: tuple[type[E], ...],
    ) -> tuple[E | None, ValidationResult]:
        if not isinstance(value, error_types):
            return None, _failure(TypeError("undeclared NodeError type"), retry=False)
        # The registered class tuple witnesses E at this erased exception boundary.
        return self.validate(value, type(value))

    def validate[T: BaseModel](
        self, value: object, contract: type[T],
    ) -> tuple[T | None, ValidationResult]:
        try:
            output = _declared_instance(value, contract)
            validate_immutable(output)
            _check_existing_models(output)
        except (ValueError, TypeError) as error:
            return None, _failure(error, retry=False)
        return output, ValidationResult(status=ValidationStatus.OK)

    def parse_json[T: BaseModel](
        self, raw: str, contract: type[T],
    ) -> tuple[T | None, ValidationResult]:
        try:
            output = _declared_instance(contract.model_validate_json(raw, strict=True), contract)
            validate_immutable(output)
        except (ValueError, TypeError) as error:
            return None, _failure(error, retry=True)
        return output, ValidationResult(status=ValidationStatus.OK)
