"""Semantic validation belongs to the callback registered in the binding."""

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class NodeValidator:
    def validate[I: BaseModel, O: BaseModel, E: NodeError](
        self, ctx: NodeValidationContext[O], contract: NodeContract[I, O, E],
    ) -> ValidationResult:
        if contract.validator is None:
            return ValidationResult(status=ValidationStatus.OK)
        return contract.validator(ctx)
