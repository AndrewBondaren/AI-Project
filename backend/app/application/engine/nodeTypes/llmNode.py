from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.application.engine.nodeTypes.baseNode import BaseNode

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True, kw_only=True)
class LLMNode(BaseNode[I, O], Generic[I, O]):
    dsl: str = ""
    temperature: float = 0.0
    enable_thinking: bool = False
