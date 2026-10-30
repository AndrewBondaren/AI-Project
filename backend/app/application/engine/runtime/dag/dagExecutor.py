"""Concurrent Python levels and synchronous barrier commit; no domain work."""

import asyncio
from collections.abc import Collection, Mapping, Callable
from time import time
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision, NodeOutcome
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationSource, ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity, Index,
)
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase, validate_python_phase
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionIdentity, NodeId, PlanRevision, PlanRevisionValue
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import OutputRecord


class DAGExecutor:
    def __init__(
        self, runner: NodeRunner, executors: Mapping[type[PythonExecutor], PythonExecutor], *,
        clock: Callable[[], float] = time,
    ) -> None:
        self._runner = runner
        self._executors = dict(executors)
        self._clock = clock

    async def run_python_phase(
        self, plan: ExecutionPlan, state: ExecutionState, phase: PythonExecutionPhase,
        plan_revision: PlanRevision, *, pass_number: Index = 0,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, rerun: Collection[NodeId] = (),
    ) -> LevelDecision:
        validate_python_phase(phase)
        TypeAdapter[int](Index).validate_python(pass_number)
        TypeAdapter[PlanRevision](PlanRevisionValue).validate_python(plan_revision)
        if set(rerun).difference(plan.nodes):
            raise KeyError("rerun contains nodes outside the plan")
        levels = plan.pre_llm_levels if phase == ExecutionPhase.PRE_LLM else plan.post_llm_levels
        for node_id in (node_id for level in levels for node_id in level):
            registration = plan.registrations[node_id]
            state.catalog.validate_binding(node_id, registration.contract)
            node = plan.get(node_id, registration.contract).node
            if not isinstance(node, PythonNode) or node.phase != phase:
                raise TypeError("Python phase contains an incompatible node")
            if registration.executor_cls not in self._executors:
                raise KeyError(f"no executor supplied for '{node_id}'")
            if not isinstance(self._executors[registration.executor_cls], registration.executor_cls):
                raise TypeError(f"executor does not match binding '{node_id}'")
        if phase == ExecutionPhase.POST_LLM and state.decision != LevelDecision.CONTINUE:
            return state.decision
        state.begin_phase()
        try:
            state.catalog.invalidate_for_reuse(confirmed_domain_revisions or {})
            state.begin_level(())
            for level, node_ids in enumerate(levels):
                snapshot = await self._run_level(plan, state, phase, plan_revision, pass_number, level, node_ids, rerun)
                if snapshot.decision != LevelDecision.CONTINUE:
                    return snapshot.decision
            return LevelDecision.CONTINUE
        finally:
            state.end_phase()

    async def _run_level(
        self, plan: ExecutionPlan, state: ExecutionState, phase: PythonExecutionPhase,
        revision: PlanRevision, pass_number: int, level: int, node_ids: tuple[NodeId, ...], rerun: Collection[NodeId],
    ) -> ExecutionLevelSnapshot:
        started_at = self._clock()
        current = {identity.node_id: identity for identity in state.catalog.current_outputs}
        attempts: list[ExecutionIdentity] = []
        reused: list[ExecutionIdentity] = []
        for node_id in node_ids:
            node = self._python_node(plan, node_id)
            last_pass = state.last_pass(node_id)
            new_pass = pass_number > 0 and (last_pass is None or last_pass < pass_number)
            if node_id in current and node_id not in rerun and (not new_pass or node.skip_on_replan):
                reused.append(current[node_id])
            else:
                attempts.append(state.catalog.begin_attempt(node_id, revision))
        identities = tuple(attempts)
        state.begin_level(identities)
        views = tuple(state.catalog.read_view(identity.node_id) for identity in identities)
        tasks = tuple(asyncio.create_task(self._run_node(plan, view, identity, pass_number, level))
                      for identity, view in zip(identities, views, strict=True))
        group = asyncio.gather(*tasks, return_exceptions=True)
        cancel_requested_at: float | None = None
        try:
            results = await asyncio.shield(group)
        except asyncio.CancelledError:
            cancel_requested_at = self._clock()
            for task in tasks:
                if not task.done():
                    task.cancel()
            while True:
                try:
                    results = await asyncio.shield(group)
                    break
                except asyncio.CancelledError:
                    # A repeated parent request must not cancel child cleanup.
                    pass
        outcomes = tuple(
            self._normalize(result, identity, view, phase, pass_number, level, started_at)
            for result, identity, view in zip(results, identities, views, strict=True)
        )
        # No await in publication or metadata updates: peers only become
        # visible after all tasks have finished and their outcomes are known.
        committed: list[NodeOutcome[BaseModel, NodeError]] = []
        saved: list[ExecutionIdentity] = []
        for outcome, view in zip(outcomes, views, strict=True):
            registration = plan.registrations[outcome.identity.node_id]
            try:
                if outcome.output is not None:
                    state.catalog.publish(OutputRecord[BaseModel](
                        identity=outcome.identity, contract_id=registration.contract.contract_id,
                        contract_version=registration.contract.version, output=outcome.output,
                        reads=outcome.reads, domain_reads=outcome.domain_reads,
                    ))
                    saved.append(outcome.identity)
                elif outcome.error is not None:
                    state.catalog.close_error(outcome.identity, outcome.error, registration.contract)
                else:
                    state.catalog.close_attempt(outcome.identity)
            except Exception as error:
                outcome = self._failure(outcome.identity, view, phase, pass_number, level, started_at,
                                        NodeStatus.FAILED, f"publication: {type(error).__name__}")
                state.catalog.close_attempt(outcome.identity)
            committed.append(outcome)
        statuses = {outcome.status for outcome in committed}
        gate_count = sum(outcome.gate is not None for outcome in committed)
        if cancel_requested_at is not None or NodeStatus.CANCELLED in statuses:
            decision = LevelDecision.CANCEL
        elif NodeStatus.FAILED in statuses or gate_count > 1:
            decision = LevelDecision.FAIL
        elif gate_count:
            decision = LevelDecision.REPLAN
        else:
            decision = LevelDecision.CONTINUE
        snapshot = ExecutionLevelSnapshot(
            phase, pass_number, level, decision, tuple(ExecutionTrace.from_outcome(outcome) for outcome in committed),
            tuple(saved), tuple(reused), cancel_requested_at, self._clock(),
        )
        state.finish_level(snapshot)
        return snapshot

    @staticmethod
    def _python_node(plan: ExecutionPlan, node_id: NodeId) -> PythonNode[BaseModel, BaseModel, NodeError]:
        registration = plan.registrations[node_id]
        node = plan.get(node_id, registration.contract).node
        if not isinstance(node, PythonNode):
            raise TypeError("Python phase requires PythonNode")
        return node

    async def _run_node(
        self, plan: ExecutionPlan, view: PublishedDAGReadView, identity: ExecutionIdentity, pass_number: int, level: int,
    ) -> NodeOutcome[BaseModel, NodeError]:
        registration = plan.registrations[identity.node_id]
        if registration.executor_cls is None:
            raise TypeError("Python binding has no executor")
        return await self._runner.run(self._python_node(plan, identity.node_id), view, identity, registration,
                                      self._executors[registration.executor_cls], pass_number=pass_number, level=level)

    def _normalize(
        self, result: object, identity: ExecutionIdentity, view: PublishedDAGReadView,
        phase: PythonExecutionPhase, pass_number: int, level: int, started_at: float,
    ) -> NodeOutcome[BaseModel, NodeError]:
        result_name = type(result).__name__
        if isinstance(result, NodeOutcome) and result.identity == identity:
            # Only the private bound runner tasks supply successful outcomes;
            # catalog commit additionally checks actual classes/contracts.
            admitted = cast(NodeOutcome[BaseModel, NodeError], result)
            try:
                admitted.__post_init__()
                return admitted
            except (TypeError, ValueError):
                pass
        status = NodeStatus.CANCELLED if isinstance(result, asyncio.CancelledError) else NodeStatus.FAILED
        return self._failure(identity, view, phase, pass_number, level, started_at, status, result_name)

    def _failure(
        self, identity: ExecutionIdentity, view: PublishedDAGReadView, phase: PythonExecutionPhase,
        pass_number: int, level: int, started_at: float, status: NodeStatus, message: str,
    ) -> NodeOutcome[BaseModel, NodeError]:
        completed_at = self._clock()
        cancelled = status == NodeStatus.CANCELLED
        diagnostic = ExecutionDiagnostic(
            identity=identity, pass_number=pass_number, phase=phase, level=level, timestamp=completed_at,
            code=ExecutionEventCode.CANCEL_OBSERVED if cancelled else ExecutionEventCode.NODE_FINISHED,
            severity=ExecutionSeverity.INFO if cancelled else ExecutionSeverity.ERROR, status=status, message=message,
            reads=view.dependency_reads, completed_at=completed_at,
            cancel_source=CancellationSource.UNKNOWN if cancelled else None,
            cancel_reason=CancellationReason.UNKNOWN if cancelled else None,
            cancel_observed_at=completed_at if cancelled else None,
        )
        return NodeOutcome[BaseModel, NodeError](
            identity=identity, status=status, started_at=started_at, completed_at=completed_at,
            reads=view.dependency_reads, domain_reads=view.domain_reads, diagnostics=(diagnostic,),
        )
