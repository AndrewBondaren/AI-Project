from typing import Type
from app.application.engine.nodes.nodeRegistration import NodeRegistration


class NodeRegistry:

    def __init__(self):
        self._nodes: dict[str, NodeRegistration] = {}

    def register(self, node_cls: Type, executor_cls: Type):
        node_id = getattr(node_cls, "id", None)

        if not node_id:
            raise ValueError(f"Node {node_cls.__name__} missing id")

        if not executor_cls:
            raise ValueError(f"Node {node_cls.__name__} missing executor")

        # инстанциируем чтобы проверить поля
        try:
            node = node_cls()
        except Exception as e:
            raise ValueError(f"Node {node_cls.__name__} cannot be instantiated: {e}")

        # если есть contract_json — обязан быть validator
        contract = getattr(node, "contract_json", None)
        validator = getattr(node, "validator", None)

        if contract and not validator:
            raise ValueError(
                f"Node '{node.id}' has contract_json={contract.__name__} "
                f"but no validator — add validator to the node"
            )

        # если есть validator — обязан быть contract_json
        if validator and not contract:
            raise ValueError(
                f"Node '{node.id}' has validator={validator.__name__} "
                f"but no contract_json — add contract_json or remove validator"
            )

        self._nodes[node.id] = NodeRegistration(
            node_cls=node_cls,
            executor_cls=executor_cls
        )

        return node_cls

    def get(self, node_id: str) -> NodeRegistration:
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not registered")
        return self._nodes[node_id]

    def all(self) -> dict[str, NodeRegistration]:
        return self._nodes


NODE_REGISTRY = NodeRegistry()


def register(executor_cls: Type):
    def decorator(node_cls: Type):
        NODE_REGISTRY.register(node_cls, executor_cls=executor_cls)
        return node_cls
    return decorator