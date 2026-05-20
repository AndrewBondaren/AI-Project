from __future__ import annotations
from app.application.engine.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.dag.executionTrace import ExecutionTrace


class ExecutionState:

    def __init__(self, message: str, session):

        #request context (read-only после init)
        self.message = message
        self.session = session
        self.task_type = None

        #execution data (пишут NodeRunner + LLMAggregateExecutor)
        self.node_status: dict[str, str] = {}
        self.node_results: dict[str, object] = {}
        self.node_errors: dict[str, list] = {}
        self.shared_context: dict = {}
        self.execution_order: list[str] = []

        #control flow (пишут ноды, читает DAGExecutor)
        self.pending_patches: list[dict] = []
        self.requires_replan: bool = False
        self.replan_reason: str | None = None

        #observability (append-only)
        self.traces: list[ExecutionTrace] = []
        self.snapshots: list[ExecutionLevelSnapshot] = []

        #infrastructure 
        self.cancel_token = None  # CancellationToken | None

        #final output
        self.final_result = None