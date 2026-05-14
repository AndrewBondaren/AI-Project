from app.application.engine.dag.StateSnapshot import StateSnapshot


class ExecutionState:

    def __init__(self, message: str, session):

        self.message = message
        self.session = session

        self.node_status = {}
        self.node_results = {}
        self.node_errors = {}

        self.shared_context = {}

        self.snapshots: list[StateSnapshot] = []