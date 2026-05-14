from typing import Type


class NodeRegistry:

    def __init__(self):
        self._nodes: dict[str, Type] = {}

    def register(self, cls: Type):
        node_id = getattr(cls, "id", None)

        if not node_id:
            raise ValueError("Node missing id")

        self._nodes[node_id] = cls
        return cls

    def get(self, node_id: str):
        return self._nodes[node_id]

    def all(self):
        return self._nodes