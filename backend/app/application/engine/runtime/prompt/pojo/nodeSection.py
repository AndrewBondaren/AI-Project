"""A prepared Input with its owning schemas; payloads stay POJO until wire."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.dataModel.engine.dag.identity import NodeId, NodeIdValue

I = TypeVar("I", bound=BaseModel, covariant=True)


@dataclass(frozen=True, kw_only=True)
class NodeSection(Generic[I]):
    node_id: NodeId
    dsl: str
    input_type: type[I]
    input: I
    output_type: type[BaseModel]

    def __post_init__(self) -> None:
        TypeAdapter[NodeId](NodeIdValue).validate_python(self.node_id)
        for model in (self.input_type, self.output_type):
            TypeAdapter(type[BaseModel]).validate_python(model)
        admitted, validation = ContractValidator().validate(self.input, self.input_type)
        if admitted is None or not validation.ok:
            raise TypeError(f"node '{self.node_id}' Input does not satisfy its immutable POJO contract")

    def to_dict(self) -> dict[str, object]:
        return {"dsl": self.dsl, "context_data": TypeAdapter(self.input_type).dump_python(self.input, mode="json")}
