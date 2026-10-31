"""LLM phase writer: whole-group attempts, cancellation barrier and batch commit."""

import asyncio
from collections.abc import Callable, Collection, Mapping
from time import time

from pydantic import BaseModel

from app.application.engine.diagnostics.executionEvents import ExecutionEvents
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan, LLMGroup
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision, NodeOutcome
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.dataModel.engine.dag.diagnostics import CancellationRequest, ExecutionDiagnostic, Index
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionIdentity, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import OutputRecord


class LLMGroupCoordinator:
    def __init__(self, aggregate: LLMAggregateExecutor, emit: Callable[[ExecutionDiagnostic], None], *, clock: Callable[[], float] = time) -> None:
        self._aggregate, self._emit, self._clock = aggregate, emit, clock

    async def run_phase(
        self, plan: ExecutionPlan, state: ExecutionState, revision: PlanRevision, request: LLMRequest, *,
        options: LLMExecutionOptions, pass_number: Index = 0,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None,
        rerun: Collection[NodeId] = (), cancellation: CancellationRequest | None = None,
    ) -> LevelDecision:
        options.__post_init__()
        if cancellation is not None:
            cancellation = CancellationRequest.model_validate(cancellation)
        nodes: set[NodeId] = set()
        for group in plan.llm_groups:
            members = tuple(node for row in group.levels for node in row)
            if not members or len(set(members)) != len(members) or nodes.intersection(members):
                raise ValueError("LLM groups require unique nonempty members")
            nodes.update(members)
            for node_id in members:
                registration = plan.registrations[node_id]
                state.catalog.validate_binding(node_id, registration.contract)
                node = self._aggregate.node(plan, node_id)
                if registration.kind != NodeKind.LLM or node.temperature != group.temperature:
                    raise TypeError("LLM group does not match compiled binding/temperature")
                if any(read.ref.producer in members for read in registration.contract.reads):
                    raise ValueError("LLM group cannot read a sibling Output")
        if set(rerun).difference(nodes):
            raise KeyError("LLM rerun contains nodes outside the phase")
        if not state.catalog.is_quiescent:
            raise RuntimeError("LLM phase requires a quiescent catalog")
        if state.decision != LevelDecision.CONTINUE:
            resuming_llm = state.decision == LevelDecision.CANCEL and state.levels and state.levels[-1].phase == ExecutionPhase.LLM
            if not resuming_llm:
                return state.decision
        state.begin_phase(revision, pass_number)
        try:
            state.catalog.invalidate_for_reuse(confirmed_domain_revisions or {})
            state.begin_level(())
            for level, group in enumerate(plan.llm_groups):
                snapshot = await self._run_group(plan, state, group, revision, request, options, pass_number, level, rerun, cancellation)
                if snapshot.decision != LevelDecision.CONTINUE:
                    return snapshot.decision
            return LevelDecision.CONTINUE
        finally:
            state.end_phase()

    async def _run_group(
        self, plan: ExecutionPlan, state: ExecutionState, group: LLMGroup, revision: PlanRevision,
        request: LLMRequest, options: LLMExecutionOptions, pass_number: int, level: int,
        rerun: Collection[NodeId], cancellation: CancellationRequest | None,
    ) -> ExecutionLevelSnapshot:
        started = self._clock()
        nodes = tuple(node for row in group.levels for node in row)
        current = {identity.node_id: identity for identity in state.catalog.current_outputs}
        reusable = all(node in current and state.last_pass(node) == pass_number and node not in rerun for node in nodes)
        reused = tuple(current[node] for node in nodes) if reusable else ()
        identities = () if reusable else tuple(state.catalog.begin_attempt(node, revision) for node in nodes)
        state.begin_level(identities)
        views = {identity.node_id: state.catalog.read_view(identity.node_id) for identity in identities}
        events = ExecutionEvents(ExecutionPhase.LLM, revision, pass_number, level, started,
                                 {node: view.requirements for node, view in views.items()}, self._emit, self._clock, cancellation)
        if reused:
            snapshot = ExecutionLevelSnapshot(ExecutionPhase.LLM, pass_number, level, LevelDecision.CONTINUE,
                                              (), (), reused, None, self._clock())
            state.finish_level(snapshot)
            events.finished(snapshot, {})
            return snapshot
        for identity in identities:
            events.started(identity)
        task = asyncio.create_task(self._aggregate.execute(plan, group, identities, views, request,
                                                           options=options, pass_number=pass_number, level=level))
        cancelled_at: float | None = None
        try:
            outcomes = await asyncio.shield(task)
        except asyncio.CancelledError:
            parent = asyncio.current_task()
            if parent is not None and parent.cancelling():
                cancelled_at = cancellation.requested_at if cancellation is not None and cancellation.requested_at is not None else self._clock()
                events.cancel_requested(identities, tuple(views.values()), (), cancelled_at)
            task.cancel()
            while True:
                try:
                    outcomes = await asyncio.shield(task)
                    break
                except asyncio.CancelledError:
                    if task.done():
                        if task.cancelled():
                            outcomes = self._reject(identities, views, NodeStatus.CANCELLED, started, pass_number, level, "LLM task cancelled")
                        else:
                            try:
                                outcomes = task.result()
                            except Exception as error:
                                outcomes = self._reject(identities, views, NodeStatus.FAILED, started, pass_number, level, type(error).__name__)
                        break
                except Exception as error:
                    outcomes = self._reject(identities, views, NodeStatus.FAILED, started, pass_number, level, type(error).__name__)
                    break
        except Exception as error:
            outcomes = self._reject(identities, views, NodeStatus.FAILED, started, pass_number, level, type(error).__name__)
        try:
            if tuple(outcome.identity for outcome in outcomes) != identities:
                raise ValueError("LLM outcomes do not match opened identities")
            for outcome in outcomes:
                outcome.__post_init__()
                if outcome.status == NodeStatus.GATED:
                    raise ValueError("LLM phase cannot gate")
                if outcome.error is not None:
                    _, validation = ContractValidator().validate_error(outcome.error, plan.registrations[outcome.identity.node_id].contract.error_types)
                    if not validation.ok:
                        raise TypeError("undeclared LLM preparation error")
        except Exception as error:
            outcomes = self._reject(identities, views, NodeStatus.FAILED, started, pass_number, level, type(error).__name__)
        cancelled = cancelled_at is not None or any(outcome.status == NodeStatus.CANCELLED for outcome in outcomes)
        failed = any(outcome.status != NodeStatus.SUCCESS for outcome in outcomes)
        saved: tuple[ExecutionIdentity, ...] = ()
        if not cancelled and not failed:
            try:
                records: list[OutputRecord[BaseModel]] = []
                for outcome in outcomes:
                    if outcome.output is None:
                        raise TypeError("successful group outcome requires Output")
                    contract = plan.registrations[outcome.identity.node_id].contract
                    records.append(OutputRecord[BaseModel](
                        identity=outcome.identity, contract_id=contract.contract_id, contract_version=contract.version,
                        output=outcome.output, reads=outcome.reads, domain_reads=outcome.domain_reads,
                    ))
                state.catalog.publish_batch(tuple(records))
                saved = identities
            except Exception as error:
                failed = True
                outcomes = self._reject(identities, views, NodeStatus.FAILED, started, pass_number, level, f"publication: {type(error).__name__}")
        if cancelled or failed:
            outcomes = tuple(
                self._aggregate.outcome(outcome.identity, views[outcome.identity.node_id],
                                        NodeStatus.CANCELLED if cancelled else NodeStatus.FAILED, started, pass_number, level,
                                        message="LLM group discarded") if outcome.status == NodeStatus.SUCCESS else outcome
                for outcome in outcomes
            )
            for outcome in outcomes:
                if outcome.error is not None:
                    state.catalog.close_error(outcome.identity, outcome.error, plan.registrations[outcome.identity.node_id].contract)
                else:
                    state.catalog.close_attempt(outcome.identity)
        decision = LevelDecision.CANCEL if cancelled else LevelDecision.FAIL if failed else LevelDecision.CONTINUE
        snapshot = ExecutionLevelSnapshot(
            ExecutionPhase.LLM, pass_number, level, decision, tuple(ExecutionTrace.from_outcome(outcome) for outcome in outcomes),
            saved, (), cancelled_at, self._clock(),
        )
        state.finish_level(snapshot)
        events.finished(snapshot, {outcome.identity.node_id: type(outcome.error) for outcome in outcomes if outcome.error is not None})
        return snapshot

    def _reject(
        self, identities: tuple[ExecutionIdentity, ...], views: Mapping[NodeId, PublishedDAGReadView],
        status: NodeStatus, started: float, pass_number: int, level: int, message: str,
    ) -> tuple[NodeOutcome[BaseModel, NodeError], ...]:
        return tuple(self._aggregate.outcome(identity, views[identity.node_id], status, started, pass_number, level,
                                            message=message) for identity in identities)
