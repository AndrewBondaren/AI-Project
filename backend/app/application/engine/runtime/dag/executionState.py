"""Execution-local catalog and metadata; mutations are coordinator operations."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.dataModel.engine.dag.identity import ExecutionId, ExecutionIdentity, NodeId, PlanRevision, PlanRevisionValue
from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.nodeStatus import NodeStatus

if TYPE_CHECKING:
    from pydantic import BaseModel
    from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot


class ExecutionState:
    def __init__(
        self, execution_id: ExecutionId, registry: NodeRegistry, *,
        plan_revision: PlanRevision | None = None, pass_number: Index = 0,
    ) -> None:
        self.catalog = DAGContext(execution_id, registry)
        self._statuses = {node_id: NodeStatus.IDLE for node_id in registry.ids()}
        self._traces: list[ExecutionTrace] = []
        self._levels: list[ExecutionLevelSnapshot] = []
        self._attempt_passes: dict[NodeId, int] = {}
        self._decision = LevelDecision.CONTINUE
        self._active = False
        self._released = False
        self._plan_revision = plan_revision
        self._pass_number = self._validate_context(plan_revision, pass_number)

    @staticmethod
    def _validate_context(revision: PlanRevision | None, pass_number: int, *, require_revision: bool = False) -> int:
        if require_revision or revision is not None:
            TypeAdapter[PlanRevision](PlanRevisionValue).validate_python(revision)
        return TypeAdapter[int](Index).validate_python(pass_number)

    @property
    def plan_revision(self) -> PlanRevision | None:
        return self._plan_revision

    @property
    def pass_number(self) -> int:
        return self._pass_number

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_released(self) -> bool:
        return self._released

    @classmethod
    def from_snapshot[S: BaseModel](cls, snapshot: "SessionSnapshot[S]", registry: NodeRegistry) -> "ExecutionState":
        state = cls(snapshot.metadata.execution_id, registry,
                    plan_revision=snapshot.metadata.plan_revision, pass_number=snapshot.metadata.pass_number)
        state.catalog = DAGContext.from_snapshot(snapshot.catalog, registry)
        state._statuses = dict(snapshot.statuses)
        state._attempt_passes = dict(snapshot.attempt_passes)
        state._traces = list(snapshot.traces)
        state._levels = list(snapshot.levels)
        state._decision = snapshot.decision
        if state.gate != snapshot.gate:
            raise ValueError("snapshot gate does not match level control")
        return state

    def release(self) -> None:
        if self._active:
            raise RuntimeError("cannot release an active execution phase")
        self.catalog.release()
        self._released = True

    @property
    def attempt_passes(self) -> tuple[tuple[NodeId, int], ...]:
        return tuple(sorted(self._attempt_passes.items()))

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

    def begin_phase(self, plan_revision: PlanRevision, pass_number: Index = 0) -> None:
        if self._released:
            raise RuntimeError("execution ownership has been released")
        if self._active:
            raise RuntimeError("execution already has an active phase writer")
        validated_pass = self._validate_context(plan_revision, pass_number, require_revision=True)
        self._plan_revision = plan_revision
        self._pass_number = validated_pass
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
