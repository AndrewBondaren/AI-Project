from typing import Type

from app.application.engine.nodes.nodeKind import NodeKind
from app.application.engine.nodes.nodeRegistration import NodeRegistration
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.nodes.pojo.pythonNode import PythonNode


class NodeRegistry:

    def __init__(self):
        self._nodes: dict[str, NodeRegistration] = {}

    def register_python(self, node_cls: Type, executor_cls: Type) -> Type:
        return self._register(
            node_cls,
            kind=NodeKind.PYTHON,
            executor_cls=executor_cls,
        )

    def register_llm(self, node_cls: Type) -> Type:
        return self._register(
            node_cls,
            kind=NodeKind.LLM,
            executor_cls=None,
        )

    def _register(
        self,
        node_cls: Type,
        *,
        kind: NodeKind,
        executor_cls: Type | None,
    ) -> Type:
        node_id = getattr(node_cls, "id", None)
        if not node_id:
            raise ValueError(f"Node {node_cls.__name__} missing id")

        try:
            node = node_cls()
        except Exception as e:
            raise ValueError(f"Node {node_cls.__name__} cannot be instantiated: {e}") from e

        if kind == NodeKind.PYTHON:
            if executor_cls is None:
                raise ValueError(f"Python node '{node_id}' requires executor_cls")
            if not isinstance(node, PythonNode):
                raise TypeError(
                    f"Node '{node_id}' registered as PYTHON but is not a PythonNode subclass"
                )
        elif kind == NodeKind.LLM:
            if executor_cls is not None:
                raise ValueError(f"LLM node '{node_id}' must not have executor_cls")
            if not isinstance(node, LLMNode):
                raise TypeError(
                    f"Node '{node_id}' registered as LLM but is not an LLMNode subclass"
                )
        else:
            raise ValueError(f"Unknown node kind: {kind}")

        contract = getattr(node, "contract_json", None)
        validator = getattr(node, "validator", None)

        if contract and not validator:
            raise ValueError(
                f"Node '{node.id}' has contract_json={contract.__name__} "
                f"but no validator — add validator to the node"
            )

        if validator and not contract:
            raise ValueError(
                f"Node '{node.id}' has validator={validator.__name__} "
                f"but no contract_json — add contract_json or remove validator"
            )

        if node.id in self._nodes:
            raise ValueError(f"Node '{node.id}' is already registered")

        self._nodes[node.id] = NodeRegistration(
            node_cls=node_cls,
            kind=kind,
            executor_cls=executor_cls,
        )

        return node_cls

    def get(self, node_id: str) -> NodeRegistration:
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not registered")
        return self._nodes[node_id]

    def all(self) -> dict[str, NodeRegistration]:
        return self._nodes


NODE_REGISTRY = NodeRegistry()


def register_python(executor_cls: Type):
    def decorator(node_cls: Type):
        return NODE_REGISTRY.register_python(node_cls, executor_cls=executor_cls)

    return decorator


def register_llm():
    def decorator(node_cls: Type):
        return NODE_REGISTRY.register_llm(node_cls)

    return decorator


# обратная совместимость
register = register_python
