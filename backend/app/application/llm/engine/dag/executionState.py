from typing import Any, Dict, List

from app.application.llm.engine.execution.executionTrace import ExecutionTrace


class ExecutionState:
    def __init__(self, message: str, session):
        self.message = message
        self.session = session

        self.node_status: Dict[str, str] = {}
        self.node_results: Dict[str, Any] = {}
        self.node_errors: Dict[str, List[dict]] = {}
        self.execution_order = []

        self.execution_order: List[str] = []
        self.shared_context: Dict[str, Any] = {}
        self.final_result: Any = None

        self.traces: list[ExecutionTrace] = []