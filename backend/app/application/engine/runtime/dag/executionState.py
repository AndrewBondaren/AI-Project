"""Execution-local catalog and metadata; mutations are coordinator operations."""

from collections.abc import Mapping
from types import MappingProxyType

from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.dataModel.engine.dag.identity import ExecutionId, ExecutionIdentity, NodeId
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class ExecutionState:
    def __init__(self, execution_id: ExecutionId, registry: NodeRegistry) -> None:
        self.catalog = DAGContext(execution_id, registry)
        self._statuses = {node_id: NodeStatus.IDLE for node_id in registry.ids()}
        self._traces: list[ExecutionTrace] = []
        self._levels: list[ExecutionLevelSnapshot] = []
        self._attempt_passes: dict[NodeId, int] = {}
        self._decision = LevelDecision.CONTINUE
        self._active = False

    @property
    def statuses(self) -> Mapping[NodeId, NodeStatus]:
        return MappingProxyType(self._statuses)

    @property
    def traces(self) -> tuple[ExecutionTrace, ...]:
        return tuple(self._traces)

    @property
    def levels(self) -> tuple[ExecutionLevelSnapshot, ...]:
        return tuple(self._levels)

    @property
    def decision(self) -> LevelDecision:
        return self._decision

    @property
    def gate(self) -> GateSignal | None:
        if self._decision == LevelDecision.REPLAN and self._levels:
            return self._levels[-1].gate
        return None

    def begin_phase(self) -> None:
        if self._active:
            raise RuntimeError("execution already has an active phase writer")
        self._active = True
        self._decision = LevelDecision.CONTINUE

    def last_pass(self, node_id: NodeId) -> int | None:
        return self._attempt_passes.get(node_id)

    def end_phase(self) -> None:
        self._active = False

    def begin_level(self, identities: tuple[ExecutionIdentity, ...]) -> None:
        current = {identity.node_id for identity in self.catalog.current_outputs}
        for node_id, status in self._statuses.items():
            if status == NodeStatus.SUCCESS and node_id not in current:
                self._statuses[node_id] = NodeStatus.IDLE
        for identity in identities:
            self._statuses[identity.node_id] = NodeStatus.RUNNING
        for node_id in current:
            self._statuses[node_id] = NodeStatus.SUCCESS

    def finish_level(self, snapshot: ExecutionLevelSnapshot) -> None:
        for trace in snapshot.traces:
            self._statuses[trace.identity.node_id] = trace.status
            self._attempt_passes[trace.identity.node_id] = snapshot.pass_number
        self._traces.extend(snapshot.traces)
        self._levels.append(snapshot)
        self._decision = snapshot.decision
