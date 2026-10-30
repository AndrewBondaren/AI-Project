from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.support.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.executionPhase import (
    ExecutionPhase, PythonExecutionPhase, validate_python_phase,
)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True, kw_only=True)
class PythonNode(BaseNode[I, O], Generic[I, O]):
    phase: PythonExecutionPhase = ExecutionPhase.PRE_LLM
    skip_on_replan: bool = True
    possible_errors: tuple[type[PythonNodeError], ...] = ()

    def __post_init__(self) -> None:
        validate_python_phase(self.phase)

    @abstractmethod
    async def execute(self, input: I) -> O: ...
