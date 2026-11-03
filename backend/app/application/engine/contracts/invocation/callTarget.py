from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractIdValue, ContractVersion, ContractVersionValue, NodeId, NodeIdValue


if TYPE_CHECKING:
    from app.application.engine.contracts.invocation.nodeStep import CallRequest


@dataclass(frozen=True)
class TargetSignature:
    node_id: NodeId
    contract_id: ContractId
    version: ContractVersion
    input_type: type[BaseModel]
    output_type: type[BaseModel]
    error_types: tuple[type[NodeError], ...]


@dataclass(frozen=True)
class CallTarget[I: BaseModel, O: BaseModel, E: NodeError](TargetSignature):
    input_type: type[I]
    output_type: type[O]
    error_types: tuple[type[E], ...]

    def request(self, key: CallKey, input: I) -> CallRequest[I, O, E]:
        from app.application.engine.contracts.invocation.nodeStep import CallRequest
        return CallRequest(key, self, input)

    def __post_init__(self) -> None:
        TypeAdapter(NodeIdValue).validate_python(self.node_id)
        TypeAdapter(ContractIdValue).validate_python(self.contract_id)
        TypeAdapter(ContractVersionValue).validate_python(self.version)
        for model in (self.input_type, self.output_type):
            TypeAdapter(type[BaseModel]).validate_python(model)
