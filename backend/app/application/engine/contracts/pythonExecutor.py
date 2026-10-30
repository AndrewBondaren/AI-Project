"""Executor port; runtime delegation is implemented in A2.3."""

from typing import Protocol

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.pythonNode import PythonNode


class PythonExecutor(Protocol):
    async def execute[I: BaseModel, O: BaseModel, E: NodeError](
        self, node: PythonNode[I, O, E], input: I,
    ) -> O: ...
