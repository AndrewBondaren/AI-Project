from app.dataModel.engine.dag.nodeStatus import NodeStatus


class NodeRuntimeState:

    def __init__(self):
        self.status = NodeStatus.IDLE
        self.last_error = None
        self.attempts = 0
