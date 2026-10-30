from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, FiniteFloat, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.baseNode import BaseNode

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


@dataclass(frozen=True, kw_only=True)
class LLMNode(BaseNode[I, O, E], Generic[I, O, E]):
    dsl: str = ""
    temperature: FiniteFloat = 0.0
    enable_thinking: bool = False

    def __post_init__(self) -> None:
        TypeAdapter(FiniteFloat).validate_python(self.temperature, strict=True)
