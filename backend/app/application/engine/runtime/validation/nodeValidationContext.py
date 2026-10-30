"""Typed semantic-validation input; no world lookup or runtime writes."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.identity import ExecutionIdentity

O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True)
class NodeValidationContext(Generic[O]):
    output: O
    identity: ExecutionIdentity
    pass_number: Index = 0
    repair_attempt: Index = 0

    def __post_init__(self) -> None:
        TypeAdapter[int](Index).validate_python(self.pass_number)
        TypeAdapter[int](Index).validate_python(self.repair_attempt)
