"""Project lifecycle metadata into diagnostic POJO; never inspect node payloads."""

from collections.abc import Callable, Mapping

from app.application.engine.diagnostics.events import LevelDiagnostic, ReplanDiagnostic
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.dataModel.engine.dag.diagnostics import (
    CancellationRequest, CancellationSource, CancellationReason, ExecutionDiagnostic,
    ExecutionEventCode, ExecutionSeverity, OutputRequirement,
)
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import ExecutionIdentity, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class ExecutionEvents:
    def __init__(
        self, phase: ExecutionPhase, revision: PlanRevision, pass_number: int, level: int,
        started_at: float, requirements: Mapping[NodeId, tuple[OutputRequirement, ...]],
        sink: Callable[[ExecutionDiagnostic], None], clock: Callable[[], float],
        cancellation: CancellationRequest | None,
    ) -> None:
        self._phase, self._revision = phase, revision
        self._pass, self._level = pass_number, level
        self._started_at = started_at
        self._requirements = dict(requirements)
        self._sink, self._clock = sink, clock
        self._cancellation = cancellation or CancellationRequest()

    def started(self, identity: ExecutionIdentity) -> None:
        timestamp = self._clock()
        self._sink(ExecutionDiagnostic(
            identity=identity, pass_number=self._pass, phase=self._phase, level=self._level,
            timestamp=timestamp, code=ExecutionEventCode.NODE_STARTED, severity=ExecutionSeverity.INFO,
            status=NodeStatus.RUNNING, message="node attempt started", started_at=timestamp,
            active_plan_revision=self._revision, requirements=self._requirements[identity.node_id],
        ))

    def cancel_requested(
        self, identities: tuple[ExecutionIdentity, ...], views: tuple[PublishedDAGReadView, ...],
        reused: tuple[ExecutionIdentity, ...], requested_at: float,
    ) -> None:
        anchor = (identities or reused)[0]
        self._sink(ExecutionDiagnostic(
            identity=anchor, pass_number=self._pass, phase=self._phase, level=self._level,
            timestamp=self._clock(), code=ExecutionEventCode.CANCEL_REQUESTED, severity=ExecutionSeverity.WARNING,
            status=NodeStatus.CANCELLED, message="parent cancellation requested", started_at=self._started_at,
            active_plan_revision=self._revision, cancel_requested_at=requested_at,
            cancel_source=self._cancellation.source, cancel_reason=self._cancellation.reason,
            cancel_message=self._cancellation.message,
            requirements=tuple(req for reqs in self._requirements.values() for req in reqs),
            reads=tuple(read for view in views for read in view.dependency_reads),
            domain_reads=tuple(read for view in views for read in view.domain_reads), reused_outputs=reused,
            sibling_statuses=tuple((identity.node_id, NodeStatus.RUNNING) for identity in identities)
                             + tuple((identity.node_id, NodeStatus.SUCCESS) for identity in reused),
        ))

    def finished(self, snapshot: ExecutionLevelSnapshot, error_types: Mapping[NodeId, type[NodeError]]) -> None:
        siblings = tuple((trace.identity.node_id, trace.status) for trace in snapshot.traces)
        siblings += tuple((identity.node_id, NodeStatus.SUCCESS) for identity in snapshot.reused_outputs)
        node_events: list[ExecutionDiagnostic] = []
        gate_events: list[ReplanDiagnostic] = []
        for trace in snapshot.traces:
            event = self._node_finished(trace, snapshot, siblings, error_types.get(trace.identity.node_id))
            node_events.append(event)
            if trace.status == NodeStatus.CANCELLED:
                self._sink(ExecutionDiagnostic.model_validate(dict(event) | {
                    "code": ExecutionEventCode.CANCEL_OBSERVED,
                    "timestamp": event.cancel_observed_at if event.cancel_observed_at is not None else trace.completed_at,
                }))
            self._sink(event)
            if trace.gate is not None:
                replan = ReplanDiagnostic.model_validate(dict(event) | {
                    "code": ExecutionEventCode.REPLAN_REQUESTED,
                    "next_task_type": trace.gate.next_task_type, "replan_reason": trace.gate.reason,
                })
                gate_events.append(replan)
                self._sink(replan)
        anchor = (tuple(trace.identity for trace in snapshot.traces) or snapshot.reused_outputs)[0]
        status = {
            LevelDecision.CONTINUE: NodeStatus.SUCCESS, LevelDecision.CANCEL: NodeStatus.CANCELLED,
            LevelDecision.FAIL: NodeStatus.FAILED, LevelDecision.REPLAN: NodeStatus.GATED,
        }[snapshot.decision]
        severity = self._severity(status)
        if snapshot.gate_conflict or any(trace.status == NodeStatus.FAILED for trace in snapshot.traces):
            severity = ExecutionSeverity.ERROR
        cancelled = status == NodeStatus.CANCELLED
        parent = snapshot.cancel_requested_at is not None
        observed = next((event for event in node_events if event.status == NodeStatus.CANCELLED), None)
        self._sink(LevelDiagnostic(
            identity=anchor, pass_number=self._pass, phase=self._phase, level=self._level,
            timestamp=snapshot.completed_at, code=ExecutionEventCode.LEVEL_FINISHED,
            severity=severity, status=status, message="level committed", active_plan_revision=self._revision,
            started_at=self._started_at, completed_at=snapshot.completed_at,
            requirements=tuple(req for reqs in self._requirements.values() for req in reqs),
            reads=tuple(read for trace in snapshot.traces for read in trace.reads),
            domain_reads=tuple(read for trace in snapshot.traces for read in trace.domain_reads),
            saved_outputs=snapshot.saved_outputs, reused_outputs=snapshot.reused_outputs, sibling_statuses=siblings,
            cancel_requested_at=snapshot.cancel_requested_at,
            cancel_source=(self._cancellation.source if parent else observed.cancel_source if observed else CancellationSource.UNKNOWN) if cancelled else None,
            cancel_reason=(self._cancellation.reason if parent else observed.cancel_reason if observed else CancellationReason.UNKNOWN) if cancelled else None,
            cancel_message=self._cancellation.message if parent else observed.cancel_message if observed else None,
            cancel_observed_at=min((event.cancel_observed_at for event in node_events if event.cancel_observed_at is not None), default=None),
            causes=tuple(node_events), gate_events=tuple(gate_events), gate_conflict=snapshot.gate_conflict,
        ))

    def _node_finished(
        self, trace: ExecutionTrace, snapshot: ExecutionLevelSnapshot, siblings: tuple[tuple[NodeId, NodeStatus], ...],
        error_type: type[NodeError] | None,
    ) -> ExecutionDiagnostic:
        local = next((event for event in trace.diagnostics if event.cancel_observed_at is not None), None)
        parent = snapshot.cancel_requested_at is not None
        cancelled = parent or trace.status == NodeStatus.CANCELLED
        source = self._cancellation.source if parent else local.cancel_source if local else None
        reason = self._cancellation.reason if parent else local.cancel_reason if local else None
        return ExecutionDiagnostic(
            identity=trace.identity, pass_number=self._pass, phase=self._phase, level=self._level,
            timestamp=snapshot.completed_at, code=ExecutionEventCode.NODE_FINISHED,
            severity=self._severity(trace.status), status=trace.status,
            message=f"node attempt committed: {error_type.__module__}.{error_type.__qualname__}" if error_type is not None else "node attempt committed",
            active_plan_revision=self._revision, started_at=trace.started_at, completed_at=trace.completed_at,
            requirements=self._requirements[trace.identity.node_id], reads=trace.reads, domain_reads=trace.domain_reads,
            saved_outputs=(trace.identity,) if trace.identity in snapshot.saved_outputs else (),
            sibling_statuses=siblings, causes=trace.diagnostics, cancel_requested_at=snapshot.cancel_requested_at,
            cancel_source=(source or CancellationSource.UNKNOWN) if cancelled else None,
            cancel_reason=(reason or CancellationReason.UNKNOWN) if cancelled else None,
            cancel_message=self._cancellation.message if parent else local.cancel_message if local else None,
            cancel_observed_at=local.cancel_observed_at if local else None,
        )

    @staticmethod
    def _severity(status: NodeStatus) -> ExecutionSeverity:
        if status == NodeStatus.FAILED:
            return ExecutionSeverity.ERROR
        if status == NodeStatus.CANCELLED:
            return ExecutionSeverity.WARNING
        return ExecutionSeverity.INFO
