"""Executor port; runtime delegation is implemented in A2.3."""

from typing import Protocol

from pydantic import BaseModel

from app.application.engine.nodeTypes.pythonNode import PythonNode


class PythonExecutor(Protocol):
    async def execute[I: BaseModel, O: BaseModel](
        self, node: PythonNode[I, O], input: I,
    ) -> O: ...
