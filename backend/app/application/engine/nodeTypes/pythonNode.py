from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.baseNode import BaseNode
from app.dataModel.engine.dag.executionPhase import (
    ExecutionPhase, PythonExecutionPhase, validate_python_phase,
)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


@dataclass(frozen=True, kw_only=True)
class PythonNode(BaseNode[I, O, E], Generic[I, O, E]):
    phase: PythonExecutionPhase = ExecutionPhase.PRE_LLM
    skip_on_replan: bool = True

    def __post_init__(self) -> None:
        validate_python_phase(self.phase)

    @abstractmethod
    async def execute(self, input: I) -> O: ...
