from abc import abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

from app.application.engine.contracts.invocation.nodeStep import NodeStep
from app.application.engine.contracts.invocation.resumeEvent import ResumeEvent
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase, validate_python_phase


@dataclass(frozen=True, kw_only=True)
class ResumablePythonNode[I: BaseModel, O: BaseModel, E: NodeError, S: BaseModel](BaseNode[I, O, E]):
    phase: PythonExecutionPhase = ExecutionPhase.PRE_LLM
    skip_on_replan: bool = True

    def __post_init__(self) -> None:
        validate_python_phase(self.phase)

    @abstractmethod
    async def start(self, input: I) -> NodeStep[O, S]: ...

    @abstractmethod
    async def resume(self, state: S, event: ResumeEvent) -> NodeStep[O, S]: ...
