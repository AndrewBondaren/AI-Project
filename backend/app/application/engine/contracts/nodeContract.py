"""Node I/O binding; POJO classes remain the only schema owners."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.identity import (
    ContractId, ContractIdValue, ContractVersion, ContractVersionValue,
)

if TYPE_CHECKING:
    from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
O_contra = TypeVar("O_contra", bound=BaseModel, contravariant=True)


def _validate_reads(value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError("reads must be an immutable tuple of explicit declarations")
    for requirement in cast(tuple[object, ...], value):
        if not isinstance(requirement, (RequiredOutput, OptionalOutput)):
            raise TypeError("reads must contain RequiredOutput or OptionalOutput")


class OutputLifecycle(Protocol[O_contra]):
    async def validate_restored(self, output: O_contra, /) -> None: ...


@dataclass(frozen=True)
class NodeContract(Generic[I, O]):
    input_type: type[I]
    output_type: type[O]
    contract_id: ContractId
    version: ContractVersion
    reads: tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...]
    lifecycle: OutputLifecycle[O] | None = None
    validator: Callable[["NodeValidationContext[O]"], ValidationResult] | None = None

    def __post_init__(self) -> None:
        for model in (self.input_type, self.output_type):
            TypeAdapter(type[BaseModel]).validate_python(model)
        TypeAdapter[ContractId](ContractIdValue).validate_python(self.contract_id)
        TypeAdapter[ContractVersion](ContractVersionValue).validate_python(self.version)
        _validate_reads(self.reads)
