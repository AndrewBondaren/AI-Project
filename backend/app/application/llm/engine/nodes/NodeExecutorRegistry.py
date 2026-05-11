class NodeExecutorRegistry:
    def __init__(self):
        self._executors = {}

    def register(self, node_type: str, executor):
        self._executors[node_type] = executor

    def get(self, node_type: str):
        if node_type not in self._executors:
            raise ValueError(f"No executor for type: {node_type}")
        return self._executors[node_type]