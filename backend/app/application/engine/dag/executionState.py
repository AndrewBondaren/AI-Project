from app.application.engine.dag.stateSnapshot import StateSnapshot
from app.application.engine.dag.executionTrace import ExecutionTrace


class ExecutionState:

    def __init__(self, message: str, session):

        self.message = message
        self.session = session
        self.task_type = None

        self.node_status: dict[str, str] = {}
        self.node_results: dict[str, object] = {}
        self.node_errors: dict[str, list] = {}

        self.shared_context: dict = {}

        self.execution_order: list[str] = []
        self.traces: list[ExecutionTrace] = []
        self.snapshots: list[StateSnapshot] = []

        self.pending_patches: list[dict] = []
        self.requires_replan: bool = False
        self.replan_reason: str | None = None

        self.final_result = None