"""Explicit typed registry. Importing it never registers production nodes."""

from collections.abc import Callable
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.dataModel.engine.dag.identity import NodeId, NodeIdValue


def _check_node_class(value: object, kind: NodeKind) -> None:
    expected = PythonNode if kind is NodeKind.PYTHON else LLMNode
    if not isinstance(value, type) or not issubclass(value, expected):
        raise TypeError(f"{kind.value} registration requires a {expected.__name__} class")


def _check_binding(contract: object, executor_cls: object, kind: NodeKind) -> None:
    if not isinstance(contract, NodeContract):
        raise TypeError("NodeContract is mandatory")
    if kind is NodeKind.PYTHON:
        if not isinstance(executor_cls, type) or not callable(getattr(executor_cls, "execute", None)):
            raise TypeError("Python registration requires an executor class")


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[NodeId, object] = {}

    def register_python[I: BaseModel, O: BaseModel](
        self, node_cls: type[PythonNode[I, O]], executor_cls: type[PythonExecutor],
        contract: NodeContract[I, O],
    ) -> type[PythonNode[I, O]]:
        self._register(node_cls, NodeKind.PYTHON, contract, executor_cls)
        return node_cls

    def register_llm[I: BaseModel, O: BaseModel](
        self, node_cls: type[LLMNode[I, O]], contract: NodeContract[I, O],
    ) -> type[LLMNode[I, O]]:
        self._register(node_cls, NodeKind.LLM, contract, None)
        return node_cls

    def _register[I: BaseModel, O: BaseModel](
        self, node_cls: type[BaseNode[I, O]], kind: NodeKind,
        contract: NodeContract[I, O], executor_cls: type[PythonExecutor] | None,
    ) -> None:
        _check_node_class(node_cls, kind)
        _check_binding(contract, executor_cls, kind)
        node_id = TypeAdapter[NodeId](NodeIdValue).validate_python(getattr(node_cls, "id", None))
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' is already registered")
        self._nodes[node_id] = NodeRegistration(node_id, node_cls, kind, contract, executor_cls)

    def get[I: BaseModel, O: BaseModel](
        self, node_id: NodeId, contract: NodeContract[I, O],
    ) -> NodeRegistration[I, O]:
        entry = self._nodes[node_id]
        # Only _register writes this private heterogeneous store. The exact
        # contract identity witnesses I/O before restoring the generic type.
        erased = cast(NodeRegistration[BaseModel, BaseModel], entry)
        if erased.contract is not contract:
            raise TypeError(f"contract does not match registered binding '{node_id}'")
        return cast(NodeRegistration[I, O], entry)

    def ids(self) -> tuple[NodeId, ...]:
        return tuple(self._nodes)


def register_python[I: BaseModel, O: BaseModel](
    executor_cls: type[PythonExecutor], contract: NodeContract[I, O], *, registry: NodeRegistry,
) -> Callable[[type[PythonNode[I, O]]], type[PythonNode[I, O]]]:
    def decorate(node_cls: type[PythonNode[I, O]]) -> type[PythonNode[I, O]]:
        return registry.register_python(node_cls, executor_cls, contract)
    return decorate


def register_llm[I: BaseModel, O: BaseModel](
    contract: NodeContract[I, O], *, registry: NodeRegistry,
) -> Callable[[type[LLMNode[I, O]]], type[LLMNode[I, O]]]:
    def decorate(node_cls: type[LLMNode[I, O]]) -> type[LLMNode[I, O]]:
        return registry.register_llm(node_cls, contract)
    return decorate
