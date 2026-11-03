"""Node I/O binding; POJO classes remain the only schema owners."""

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, cast

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.invocation.inputWait import InputWaitContract
from app.application.engine.contracts.invocation.callTarget import CallTarget, TargetSignature
from app.application.engine.contracts.invocation.continuationContract import ContinuationContract
from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.identity import (
    ContractId, ContractIdValue, ContractVersion, ContractVersionValue,
)

if TYPE_CHECKING:
    from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
    from app.application.engine.runtime.execution.nodeOutcome import GateSignal

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)
O_contra = TypeVar("O_contra", bound=BaseModel, contravariant=True)


def _validate_reads(value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError("reads must be an immutable tuple of explicit declarations")
    for requirement in cast(tuple[object, ...], value):
        if not isinstance(requirement, (RequiredOutput, OptionalOutput)):
            raise TypeError("reads must contain RequiredOutput or OptionalOutput")


def _validate_calls(value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError("calls requires immutable CallTarget declarations")
    seen: set[str] = set()
    for item in cast(tuple[object, ...], value):
        if not isinstance(item, CallTarget) or item.node_id in seen:
            raise TypeError("calls requires distinct CallTarget declarations")
        seen.add(item.node_id)
        _validate_error_types(cast(CallTarget[BaseModel, BaseModel, NodeError], item).error_types)


def _validate_error_types(value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError("error_types must be an immutable tuple of NodeError classes")
    for model in cast(tuple[object, ...], value):
        if not isinstance(model, type) or not issubclass(model, NodeError) or model is NodeError:
            raise TypeError("error_types must contain concrete NodeError classes")


class OutputLifecycle(Protocol[O_contra]):
    async def validate_restored(self, output: O_contra, /) -> None: ...


@dataclass(frozen=True)
class NodeContract(Generic[I, O, E]):
    input_type: type[I]
    output_type: type[O]
    contract_id: ContractId
    version: ContractVersion
    reads: tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...]
    error_types: tuple[type[E], ...] = field(kw_only=True)
    calls: tuple[TargetSignature, ...] = field(default=(), kw_only=True)
    continuation: ContinuationContract[BaseModel] | None = field(default=None, kw_only=True)
    input_wait: InputWaitContract[BaseModel, BaseModel] | None = field(default=None, kw_only=True)
    retry_policy: Callable[[E, int], bool] | None = field(default=None, kw_only=True)
    error_policy: Callable[[E], "GateSignal | None"] | None = field(default=None, kw_only=True)
    lifecycle: OutputLifecycle[O] | None = None
    validator: Callable[["NodeValidationContext[O]"], ValidationResult] | None = None

    def __post_init__(self) -> None:
        for model in (self.input_type, self.output_type):
            TypeAdapter(type[BaseModel]).validate_python(model)
        TypeAdapter[ContractId](ContractIdValue).validate_python(self.contract_id)
        TypeAdapter[ContractVersion](ContractVersionValue).validate_python(self.version)
        _validate_reads(self.reads)
        _validate_calls(self.calls)
        _validate_error_types(self.error_types)
        if self.error_policy is not None and not self.error_types:
            raise TypeError("error_policy requires declared error types")
