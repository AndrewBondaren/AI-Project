"""Typed transient validation failure; invalid JSON never becomes an Output."""

from dataclasses import dataclass
import json
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence
from app.dataModel.validation.immutableValue import validate_immutable

O = TypeVar("O", bound=BaseModel, covariant=True)


@dataclass(frozen=True, kw_only=True)
class NodeFailureContext(Generic[O]):
    identity: ExecutionIdentity
    validation: ValidationResult
    output_type: type[O]
    raw_output: str | None
    dsl_task: str
    dsl_keys: tuple[str, ...]
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()
    pass_number: Index = 0
    repair_attempt: Index = 0

    def __post_init__(self) -> None:
        ExecutionIdentity.model_validate(self.identity)
        TypeAdapter(type[BaseModel]).validate_python(self.output_type)
        TypeAdapter(ValidationResult).validate_python(self.validation, strict=True)
        if self.validation.ok:
            raise ValueError("repair requires an unsuccessful validation")
        TypeAdapter(str | None).validate_python(self.raw_output, strict=True)
        TypeAdapter(str).validate_python(self.dsl_task, strict=True)
        TypeAdapter(tuple[str, ...]).validate_python(self.dsl_keys, strict=True)
        TypeAdapter(Index).validate_python(self.pass_number, strict=True)
        TypeAdapter(Index).validate_python(self.repair_attempt, strict=True)
        validate_immutable((self.reads, self.domain_reads))
        for read in self.reads:
            DependencyRead.model_validate(read)
            if read.result is not None and read.result.execution_id != self.identity.execution_id:
                raise ValueError("repair read belongs to another execution")
        for read in self.domain_reads:
            DomainReadEvidence.model_validate(read)

    def to_dict(self) -> dict[str, object]:
        output: object = self.raw_output
        if self.raw_output is not None:
            try:
                output = json.loads(self.raw_output)
            except json.JSONDecodeError:
                pass
        return {
            "node_id": self.identity.node_id, "dsl_task": self.dsl_task,
            "error_codes": [error.code for error in self.validation.errors], "output": output,
            "validation": TypeAdapter(ValidationResult).dump_python(self.validation, mode="json"),
            "identity": self.identity.model_dump(mode="json"),
            "pass_number": self.pass_number, "repair_attempt": self.repair_attempt,
            "reads": TypeAdapter(tuple[DependencyRead, ...]).dump_python(self.reads, mode="json"),
            "domain_reads": TypeAdapter(tuple[DomainReadEvidence, ...]).dump_python(self.domain_reads, mode="json"),
        }
