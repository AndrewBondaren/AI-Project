"""LLM boundary sequencing only; no business rules, repair loop or publication."""

from pydantic import BaseModel

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.identity import ExecutionIdentity


class LLMValidator:
    def __init__(self, contract_validator: ContractValidator, node_validator: NodeValidator) -> None:
        self._contract_validator = contract_validator
        self._node_validator = node_validator

    def validate[I: BaseModel, O: BaseModel](
        self, raw: str, contract: NodeContract[I, O], identity: ExecutionIdentity, *,
        pass_number: Index = 0, repair_attempt: Index = 0,
    ) -> tuple[O | None, ValidationResult]:
        output, structural = self._contract_validator.parse_json(raw, contract.output_type)
        if output is None or not structural.ok:
            return None, structural
        ctx = NodeValidationContext(output, identity, pass_number, repair_attempt)
        semantic = self._node_validator.validate(ctx, contract)
        if not semantic.ok:
            return None, semantic
        return output, semantic
