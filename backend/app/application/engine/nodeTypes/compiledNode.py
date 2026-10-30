from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.baseNode import BaseNode

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


@dataclass(frozen=True)
class CompiledNode(Generic[I, O, E]):
    node: BaseNode[I, O, E]
    compiled_rules: tuple[Callable[[BaseNode[I, O, E], object], bool], ...]
