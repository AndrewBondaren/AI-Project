"""Concurrent Python levels and synchronous barrier commit; no domain work."""

import asyncio
from uuid import uuid4
from collections.abc import Collection, Mapping, Callable
from time import time
from typing import cast

from pydantic import BaseModel

from app.application.engine.diagnostics.dagLog import emit as emit_diagnostic
from app.application.engine.diagnostics.executionEvents import ExecutionEvents
from app.application.engine.contracts.invocation.executionStore import ExecutionStore, RestoreFailure
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.nodeStep import Complete
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.application.engine.runtime.invocations.stepEffect import StepEffect
from app.application.engine.runtime.invocations.ownedExecution import OwnedExecution
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.dataModel.engine.dag.invocations.record import InvocationRecord, InvocationStatus
from app.dataModel.engine.dag.identity import ExecutionId
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision, NodeOutcome
from app.application.engine.taskType import TaskType
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.dag.llm.groupCoordinator import LLMGroupCoordinator
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationRequest, CancellationSource, ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity, Index,
)
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase, validate_python_phase
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionIdentity, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import OutputRecord


class DAGExecutor:
    def __init__(
        self, runner: NodeRunner, executors: Mapping[type[PythonExecutor], PythonExecutor], *,
        invocation_options: InvocationOptions | None = None,
        clock: Callable[[], float] = time,
        emit: Callable[[ExecutionDiagnostic], None] = emit_diagnostic,
    ) -> None:
        self._invocations = invocation_options
        self._runner = runner
        self._executors = dict(executors)
        self._clock = clock
        self._emit = emit

    @property
    def invocation_options(self) -> InvocationOptions | None:
        return self._invocations

    async def run_invocation(
        self, plan: ExecutionPlan, execution_id: ExecutionId, root: NodeId, revision: PlanRevision,
        store: ExecutionStore, *, owner: str, workers: int, invocation_limit: int,
        input: BaseModel | None = None, lease_seconds: int = 300,
        prior_outputs: tuple[OutputRecord[BaseModel], ...] = (),
    ) -> InvocationRecord:
        if workers < 1:
            raise ValueError("workers must be positive")
        try:
            await store.load(execution_id)
        except KeyError:
            initial = InvocationCoordinator.create(plan, execution_id, revision, root, invocation_limit, input)
            await store.create(execution_id, CheckpointCodec.encode(initial.graph))
        claim = await store.claim(execution_id, owner, lease_seconds)
        try:
            saved = await store.load(execution_id)
            graph = await CheckpointCodec.restore(saved.blob, plan)
            if (graph.execution_id, graph.revision, graph.records[graph.root].node_id) != (execution_id, revision, root):
                raise RestoreFailure("checkpoint does not match execution plan")
            if input is not None and graph.records[graph.root].input != InvocationCoordinator.encode(
                input, plan.registrations[root].contract.input_type,
            ):
                raise RestoreFailure("execution already exists with different input")
            coordinator = InvocationCoordinator(plan, graph, invocation_limit)
            coordinator.bind_published(prior_outputs)
            return await self._schedule_invocations(coordinator, OwnedExecution(store, claim, saved.revision, graph, lease_seconds), workers)
        finally:
            await store.release(claim)

    async def _schedule_invocations(
        self, coordinator: InvocationCoordinator, owned: OwnedExecution, workers: int,
    ) -> InvocationRecord:
        graph = coordinator.graph
        root = graph.records[graph.root]
        terminal = (InvocationStatus.SUCCEEDED, InvocationStatus.FAILED, InvocationStatus.CANCELLED)
        active: dict[asyncio.Task[StepEffect], ExecutionIdentity] = {}
        try:
            while root.status not in terminal or active:
                ready = coordinator.ready()[:workers - len(active)]
                if ready:
                    for record in ready:
                        coordinator.begin(record)
                    await owned.save()
                    for record in ready:
                        active[asyncio.create_task(self._invocation_step(coordinator, record))] = record.identity()
                if not active:
                    if root.status not in terminal and InputWaitCoordinator.waiting(graph, coordinator.plan).pending:
                        graph.waiting_for_input = True
                        await owned.save()
                        break
                    if root.status not in terminal:
                        raise ValueError("invocation graph has no runnable step")
                    await owned.save()
                    break
                finished, _ = await asyncio.wait(active, timeout=owned.lease_seconds / 3,
                                                 return_when=asyncio.FIRST_COMPLETED)
                if not finished:
                    await owned.store.renew(owned.claim, owned.lease_seconds)
                for task in finished:
                    identity = active.pop(task)
                    coordinator.finish(graph.records[identity.invocation_id], identity, task.result())
                    coordinator.ready()
                    await owned.save()
        finally:
            for task in active:
                task.cancel()
            if active:
                await asyncio.gather(*active, return_exceptions=True)
        return root

    async def _invocation_step(self, coordinator: InvocationCoordinator, record: InvocationRecord) -> StepEffect:
        plan = coordinator.plan
        node = plan.nodes[record.node_id].node
        reg = plan.registrations[record.node_id]
        contract = reg.contract
        view = coordinator.view(record)
        prepared = contract.input_type.model_validate_json(record.input) if record.input is not None else None
        if isinstance(node, PythonNode) and reg.executor_cls is not None:
            admitted: list[BaseModel] = []
            outcome = await self._run_node(plan, view, record.identity(), coordinator.graph.pass_number, 0,
                                           explicit_input=prepared, on_prepared=admitted.append,
                                           apply_error_policy=record.invocation_id == coordinator.graph.root)
            return StepEffect(step=Complete(outcome.output) if outcome.output is not None else None,
                              prepared=admitted[0] if admitted else None, error=outcome.error, gate=outcome.gate,
                              diagnostics=outcome.diagnostics, cancelled=outcome.status == NodeStatus.CANCELLED,
                              reads=outcome.reads, domain_reads=outcome.domain_reads)
        elif isinstance(node, ResumablePythonNode) and contract.continuation is not None:
            resumable = cast(ResumablePythonNode[BaseModel, BaseModel, NodeError, BaseModel], node)
            state = (contract.continuation.state_type.model_validate_json(record.continuation)
                     if record.continuation is not None else None)
            event = (InputWaitCoordinator.event(coordinator.graph, plan, record) or coordinator.event(record)
                     if state is not None else None)
            return await self._runner.run_resumable(resumable, view, record.identity(), reg, prepared, state, event,
                                                    coordinator.graph.pass_number, record.invocation_id == coordinator.graph.root)
        raise TypeError("unsupported invocation binding")

    async def run_llm_phase(
        self, plan: ExecutionPlan, state: ExecutionState, plan_revision: PlanRevision,
        aggregate: LLMAggregateExecutor, request: LLMRequest, *, options: LLMExecutionOptions,
        pass_number: Index = 0, confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None,
        rerun: Collection[NodeId] = (), cancellation: CancellationRequest | None = None, invalidate_reuse: bool = True,
    ) -> LevelDecision:
        return await LLMGroupCoordinator(aggregate, self._emit, clock=self._clock).run_phase(
            plan, state, plan_revision, request, options=options, pass_number=pass_number,
            confirmed_domain_revisions=confirmed_domain_revisions, rerun=rerun, cancellation=cancellation, invalidate_reuse=invalidate_reuse,
        )

    async def run_python_phase(
        self, plan: ExecutionPlan, state: ExecutionState, phase: PythonExecutionPhase,
        plan_revision: PlanRevision, *, pass_number: Index = 0,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, rerun: Collection[NodeId] = (),
        cancellation: CancellationRequest | None = None,
        invalidate_reuse: bool = True, durable: OwnedExecution | None = None,
    ) -> LevelDecision:
        validate_python_phase(phase)
        if cancellation is not None:
            cancellation = CancellationRequest.model_validate(cancellation)
        if set(rerun).difference(plan.nodes):
            raise KeyError("rerun contains nodes outside the plan")
        levels = plan.pre_llm_levels if phase == ExecutionPhase.PRE_LLM else plan.post_llm_levels
        if plan.invocation_root is not None and any(plan.invocation_root in level for level in levels):
            return await self._run_workflow_phase(plan, state, phase, plan_revision, pass_number, levels, durable)
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
            resuming_post = (state.decision == LevelDecision.CANCEL and state.levels
                             and state.levels[-1].phase == ExecutionPhase.POST_LLM and state.pass_number == pass_number)
            if not resuming_post:
                return state.decision
        state.begin_phase(plan_revision, pass_number)
        try:
            if invalidate_reuse:
                state.catalog.invalidate_for_reuse(confirmed_domain_revisions or {})
            state.begin_level(())
            for level, node_ids in enumerate(levels):
                snapshot = await self._run_level(plan, state, phase, plan_revision, pass_number, level, node_ids, rerun, cancellation)
                if snapshot.decision != LevelDecision.CONTINUE:
                    return snapshot.decision
            return LevelDecision.CONTINUE
        finally:
            state.end_phase()

    async def _run_workflow_phase(
        self, plan: ExecutionPlan, state: ExecutionState, phase: PythonExecutionPhase, revision: PlanRevision,
        pass_number: int, levels: tuple[tuple[NodeId, ...], ...], durable: OwnedExecution | None,
    ) -> LevelDecision:
        root, options = plan.invocation_root, self._invocations
        if root is None or options is None:
            raise ValueError("invocation plan requires execution options")
        catalog = state.catalog.capture()
        earlier: list[OutputRecord[BaseModel]] = []
        for node in plan.prior_phase_dependencies(root):
            prior_output = catalog.record(node, plan.registrations[node].contract)
            if prior_output is None:
                raise RestoreFailure(f"missing prior-phase output for '{node}'")
            earlier.append(prior_output)
        state.begin_phase(revision, pass_number)
        try:
            if durable is None:
                await self.run_invocation(plan, state.catalog.execution_id, root, revision, options.store,
                                          owner=str(uuid4()), workers=options.workers,
                                          invocation_limit=options.invocation_limit, lease_seconds=options.lease_seconds,
                                          prior_outputs=tuple(earlier))
                saved = await options.store.load(state.catalog.execution_id)
                graph = CheckpointCodec.decode(saved.blob, plan)
            else:
                graph = durable.graph
                coordinator = InvocationCoordinator(plan, graph, options.invocation_limit, options.interaction)
                coordinator.bind_published(tuple(earlier))
                await self._schedule_invocations(coordinator, durable, options.workers)
            if graph.waiting_for_input:
                return LevelDecision.WAIT_INPUT
            prior = {item.invocation_id: item for item in state.catalog.current_outputs}
            for level, nodes in enumerate(levels):
                traces: list[ExecutionTrace] = []
                published: list[ExecutionIdentity] = []
                reused: list[ExecutionIdentity] = []
                decision = LevelDecision.CONTINUE
                started = self._clock()
                for node_id in nodes:
                    record = graph.records[state.catalog.instance.bindings[node_id]]
                    identity = record.identity()
                    gate = GateSignal(TaskType(record.gate_task), record.gate_reason) if record.gate_task is not None else None
                    if prior.get(identity.invocation_id) == identity:
                        reused.append(identity)
                        continue
                    attempt = state.catalog.begin_attempt(node_id, revision)
                    while attempt.attempt < identity.attempt:
                        state.catalog.close_attempt(attempt)
                        attempt = state.catalog.begin_attempt(node_id, revision)
                    if attempt != identity:
                        raise RestoreFailure("root catalog attempt differs from durable graph")
                    contract = plan.registrations[node_id].contract
                    if record.status == InvocationStatus.SUCCEEDED:
                        status = NodeStatus.SUCCESS
                        output = contract.output_type.model_validate_json(record.terminal_payload())
                        state.catalog.publish(OutputRecord[BaseModel](
                            identity=identity, contract_id=contract.contract_id, contract_version=contract.version,
                            output=output, reads=record.reads, domain_reads=record.domain_reads,
                        ))
                        published.append(identity)
                    else:
                        status = NodeStatus.CANCELLED if record.status == InvocationStatus.CANCELLED else NodeStatus.FAILED
                        decision = LevelDecision.CANCEL if status == NodeStatus.CANCELLED else LevelDecision.FAIL
                        if gate is not None:
                            status = NodeStatus.GATED
                            decision = LevelDecision.REPLAN
                        if record.error_index is None:
                            state.catalog.close_attempt(identity)
                        else:
                            error = contract.error_types[record.error_index].model_validate_json(record.terminal_payload())
                            state.catalog.close_error(identity, error, contract)
                    traces.append(ExecutionTrace(identity, status, started, self._clock(), record.reads,
                                                 record.domain_reads, record.diagnostics, gate))
                state.finish_level(ExecutionLevelSnapshot(phase, pass_number, level, decision, tuple(traces),
                                                          tuple(published), tuple(reused), None, self._clock()))
                if decision != LevelDecision.CONTINUE:
                    return decision
            return LevelDecision.CONTINUE
        finally:
            state.end_phase()

    async def _run_level(
        self, plan: ExecutionPlan, state: ExecutionState, phase: PythonExecutionPhase,
        revision: PlanRevision, pass_number: int, level: int, node_ids: tuple[NodeId, ...], rerun: Collection[NodeId],
        cancellation: CancellationRequest | None,
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
        events = ExecutionEvents(phase, revision, pass_number, level, started_at,
                                 {view.consumer: view.requirements for view in views}, self._emit, self._clock, cancellation)
        for identity in identities:
            events.started(identity)
        tasks = tuple(asyncio.create_task(self._run_node(plan, view, identity, pass_number, level))
                      for identity, view in zip(identities, views, strict=True))
        group = asyncio.gather(*tasks, return_exceptions=True)
        cancel_requested_at: float | None = None
        try:
            results = await asyncio.shield(group)
        except asyncio.CancelledError:
            cancel_requested_at = cancellation.requested_at if cancellation is not None and cancellation.requested_at is not None else self._clock()
            events.cancel_requested(identities, views, tuple(reused), cancel_requested_at)
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
        events.finished(snapshot, {outcome.identity.node_id: type(outcome.error) for outcome in committed if outcome.error is not None})
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
        *, explicit_input: BaseModel | None = None, apply_error_policy: bool = True,
        on_prepared: Callable[[BaseModel], None] | None = None,
    ) -> NodeOutcome[BaseModel, NodeError]:
        registration = plan.registrations[identity.node_id]
        if registration.executor_cls is None:
            raise TypeError("Python binding has no executor")
        return await self._runner.run(self._python_node(plan, identity.node_id), view, identity, registration,
                                      self._executors[registration.executor_cls], pass_number=pass_number, level=level,
                                      explicit_input=explicit_input, apply_error_policy=apply_error_policy, on_prepared=on_prepared)

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
