class NodeExecutorRegistry:
    def __init__(self):
        self._executors = {}

    def register(self, node_cls, executor):
        self._executors[node_cls] = executor

    def get(self, node):
        return self._executors[type(node)]