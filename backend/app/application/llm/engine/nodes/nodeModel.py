class Node:
    def __init__(self, node_id: str, node_type: str, handler=None, deps=None, meta=None):
        self.id = node_id
        self.type = node_type
        self.handler = handler
        self.deps = deps or []
        self.meta = meta or {}