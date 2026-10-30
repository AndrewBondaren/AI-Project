from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.application.engine.nodeTypes.baseNode import BaseNode

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True)
class CompiledNode(Generic[I, O]):
    node: BaseNode[I, O]
    compiled_rules: tuple[Callable[[BaseNode[I, O], object], bool], ...]
