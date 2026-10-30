"""Typed invocation only; preparation and validation belong to NodeRunner."""

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.pythonNode import PythonNode


class PythonNodeExecutor:
    async def execute[I: BaseModel, O: BaseModel, E: NodeError](self, node: PythonNode[I, O, E], input: I) -> O:
        return await node.execute(input)
