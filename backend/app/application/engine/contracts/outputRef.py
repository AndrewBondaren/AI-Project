"""Explicit producer declarations; no lookup or scheduling. SoT: node context §6.1."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.identity import NodeId, NodeIdValue

O = TypeVar("O", bound=BaseModel, covariant=True)


def _validate_ref(value: object) -> None:
    if not isinstance(value, OutputRef):
        raise TypeError("output declaration must contain an OutputRef")


@dataclass(frozen=True)
class OutputRef(Generic[O]):
    producer: NodeId
    output_type: type[O]

    def __post_init__(self) -> None:
        TypeAdapter[NodeId](NodeIdValue).validate_python(self.producer)
        TypeAdapter(type[BaseModel]).validate_python(self.output_type)


@dataclass(frozen=True)
class RequiredOutput(Generic[O]):
    ref: OutputRef[O]

    def __post_init__(self) -> None:
        _validate_ref(self.ref)


@dataclass(frozen=True)
class OptionalOutput(Generic[O]):
    ref: OutputRef[O]

    def __post_init__(self) -> None:
        _validate_ref(self.ref)
