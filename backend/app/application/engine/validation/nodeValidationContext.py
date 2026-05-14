from backend.app.application.engine.dag.executionState import ExecutionState


class NodeValidationContext:
    state: ExecutionState
    node_id: str
    output: dict