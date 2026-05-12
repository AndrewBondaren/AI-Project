from typing import Dict
from app.application.llm.engine.nodes.baseNode import BaseNode


class ExecutionGraph:
    def __init__(self, nodes: Dict[str, BaseNode]):
        self.nodes = nodes
        self._validate()

    def _validate(self):
        for node_id, node in self.nodes.items():

            if node.id != node_id:
                raise ValueError(f"Node id mismatch: {node_id} != {node.id}")

            for dep in node.deps:
                if dep not in self.nodes:
                    raise ValueError(
                        f"Missing dependency: {dep} in node {node_id}"
                    )