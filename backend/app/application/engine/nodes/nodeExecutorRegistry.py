from collections import defaultdict
from typing import Type, Any, Dict


class NodeExecutorRegistry:
    def __init__(self):
        # node_cls -> list of executors (future-proof)
        self._executors: Dict[Type, list] = defaultdict(list)

    def register(self, node_cls: Type, executor: Any):
        self._executors[node_cls].append(executor)

    def get(self, node: Any):
        node_type = type(node)

        # 1. exact match
        if node_type in self._executors and self._executors[node_type]:
            return self._executors[node_type][0]

        # 2. inheritance-safe fallback
        for cls, executors in self._executors.items():
            if isinstance(node, cls) and executors:
                return executors[0]

        # 3. hard fail with debug context
        raise KeyError(
            f"No executor found for node_type={node_type.__name__}, node={node}"
        )