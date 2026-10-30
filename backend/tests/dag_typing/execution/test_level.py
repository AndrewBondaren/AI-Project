"""A2.4: deterministic barriers, concurrency, cancellation and gate policy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import FrozenInstanceError, dataclass, field, replace
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import weakref

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from tests.dag_typing.fixtures import (
    FakeExecutor, GraphBindings, GraphRuleState, LeafOutput, NodeInput, TestNodeError, TestOtherError,
)


@dataclass(frozen=True, kw_only=True)
class LevelNode(PythonNode[NodeInput, LeafOutput, TestNodeError | TestOtherError]):
    requests: tuple[RequiredOutput[LeafOutput] | OptionalOutput[LeafOutput], ...] = ()
    job: Callable[[NodeInput], Awaitable[LeafOutput]] | None = None
    prepare: Callable[[DAGReadView], Awaitable[NodeInput]] | None = None
    calls: list[str] = field(default_factory=list, compare=False)

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        self.calls.append("prepare")
        value = 1
        for request in self.requests:
            output = view.require(request) if isinstance(request, RequiredOutput) else view.optional(request)
            value += output.value if output is not None else 0
        return await self.prepare(view) if self.prepare is not None else NodeInput(value=value)

    async def execute(self, input: NodeInput) -> LeafOutput:
        self.calls.append("execute")
        return await self.job(input) if self.job is not None else LeafOutput(value=input.value)


class LevelRoot(LevelNode):
    id = NodeId("root")


class LevelLeft(LevelNode):
    id = NodeId("left")


class LevelRight(LevelNode):
    id = NodeId("right")


class LevelTail(LevelNode):
    id = NodeId("tail")


def required(node):
    return RequiredOutput(OutputRef(NodeId(node), LeafOutput))


def gate_policy(error):
    return GateSignal(TaskType.SCENE_INIT, "test replan")


class LevelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = NodeRegistry()
        self.bindings = GraphBindings()
        self.contracts = {}
        self.events = []
        self.runner = NodeRunner(ContractValidator(), NodeValidator())
        self.executor = DAGExecutor(self.runner, {PythonNodeExecutor: PythonNodeExecutor()}, emit=lambda event: None)

    async def asyncTearDown(self):
        for event in self.events:
            event.set()

    def event(self):
        event = asyncio.Event()
        self.events.append(event)
        return event

    async def reached(self, event):
        await asyncio.wait_for(event.wait(), timeout=3)

    def node(self, cls, *, deps=(), reads=(), policy=None, **kwargs):
        contract = NodeContract[NodeInput, LeafOutput, TestNodeError | TestOtherError](
            NodeInput, LeafOutput, ContractId("test." + cls.id), ContractVersion("1"), reads,
            error_types=(TestNodeError, TestOtherError), error_policy=policy,
        )
        self.registry.register_python(cls, PythonNodeExecutor, contract)
        node = cls(id=cls.id, deps=tuple(NodeId(dep) for dep in deps), requests=reads, **kwargs)
        self.bindings.nodes[cls.id] = node
        self.contracts[cls.id] = contract
        return node

    def setup_plan(self):
        compiler = GraphCompiler(self.registry, self.bindings, compile_rules=lambda rules: (), evaluate_rules=lambda node, state: True)
        compiler.precompile()
        self.plan = compiler.compile(GraphRuleState())
        self.state = ExecutionState(ExecutionId("execution-1"), self.registry)

    async def execute(self, **kwargs):
        return await self.executor.run_python_phase(self.plan, self.state, ExecutionPhase.PRE_LLM, PlanRevision("plan-1"), **kwargs)

    def current(self):
        return {identity.node_id for identity in self.state.catalog.current_outputs}

    async def test_independent_tasks_overlap_and_early_success_waits_for_barrier(self):
        left_entered, right_entered, left_release, right_release = [self.event() for _ in range(4)]
        async def left(input):
            left_entered.set()
            await left_release.wait()
            return LeafOutput(value=2)
        async def right(input):
            right_entered.set()
            await right_release.wait()
            return LeafOutput(value=3)
        self.node(LevelLeft, job=left)
        self.node(LevelRight, job=right)
        self.node(LevelTail, deps=("left", "right"), reads=(required("left"), required("right")))
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(left_entered)
        await self.reached(right_entered)
        left_release.set()
        await asyncio.sleep(0)
        self.assertEqual(self.current(), set())
        self.assertEqual(self.state.traces, ())
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.RUNNING)
        self.assertEqual(self.bindings.nodes[NodeId("tail")].calls, [])
        right_release.set()
        self.assertEqual(await task, LevelDecision.CONTINUE)
        self.assertEqual(self.current(), {"left", "right", "tail"})
        self.assertEqual([trace.identity.node_id for trace in self.state.traces], ["left", "right", "tail"])
        self.assertEqual(len(self.state.levels[1].traces[0].reads), 2)

    async def test_different_completion_orders_have_same_ordered_metadata(self):
        results = []
        for first in ("left", "right"):
            self.setUp()
            entered = {name: self.event() for name in ("left", "right")}
            release = {name: self.event() for name in ("left", "right")}
            def job(name):
                async def run(input):
                    entered[name].set()
                    await release[name].wait()
                    return LeafOutput(value=1)
                return run
            self.node(LevelRight, job=job("right"))
            self.node(LevelLeft, job=job("left"))
            self.setup_plan()
            task = asyncio.create_task(self.execute())
            await self.reached(entered["left"])
            await self.reached(entered["right"])
            release[first].set()
            await asyncio.sleep(0)
            release["right" if first == "left" else "left"].set()
            decision = await task
            results.append((decision, tuple((trace.identity.node_id, trace.status) for trace in self.state.traces),
                            tuple(identity.node_id for identity in self.state.levels[0].saved_outputs)))
        self.assertEqual(results[0], results[1])

    async def test_failure_waits_for_peer_and_preserves_success_before_stopping(self):
        entered, release = self.event(), self.event()
        async def fail(input):
            raise RuntimeError("PRIVATE_FAILURE")
        async def peer(input):
            entered.set()
            await release.wait()
            return LeafOutput(value=8)
        self.node(LevelLeft, job=fail)
        self.node(LevelRight, job=peer)
        tail = self.node(LevelTail, deps=("left", "right"))
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(entered)
        self.assertFalse(task.done())
        release.set()
        self.assertEqual(await task, LevelDecision.FAIL)
        self.assertEqual(self.current(), {"right"})
        self.assertEqual(tail.calls, [])
        self.assertEqual(len(self.state.catalog.closed_attempts), 2)
        self.assertNotIn("PRIVATE_FAILURE", repr(self.state.traces))

    async def test_node_cancel_does_not_cancel_successful_peer(self):
        async def cancel(input):
            raise asyncio.CancelledError
        self.node(LevelLeft, job=cancel)
        self.node(LevelRight)
        self.setup_plan()
        self.assertEqual(await self.execute(), LevelDecision.CANCEL)
        self.assertEqual(self.current(), {"right"})
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.CANCELLED)

    async def test_parent_cancel_waits_for_cleanup_and_saves_already_completed_peer(self):
        entered, cleaning, release, peer_done = [self.event() for _ in range(4)]
        async def blocked(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        async def peer(input):
            peer_done.set()
            return LeafOutput(value=2)
        self.node(LevelLeft, job=blocked)
        self.node(LevelRight, job=peer)
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(entered)
        await self.reached(peer_done)
        await asyncio.sleep(0)
        task.cancel()
        await self.reached(cleaning)
        self.assertFalse(task.done())
        self.assertEqual(self.current(), set())
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        release.set()
        self.assertEqual(await task, LevelDecision.CANCEL)
        self.assertEqual(self.current(), {"right"})
        snapshot = self.state.levels[0]
        self.assertIsNotNone(snapshot.cancel_requested_at)
        self.assertEqual(len(self.state.catalog.closed_attempts), 2)
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.CANCELLED)

    async def test_single_gate_keeps_typed_error_and_stops_next_level_and_post_phase(self):
        error = TestNodeError(item_id=7)
        async def gate(input):
            raise PythonNodeError(error)
        self.node(LevelLeft, job=gate, policy=gate_policy)
        self.node(LevelRight)
        tail = self.node(LevelTail, deps=("left", "right"))
        self.node(LevelRoot, phase=ExecutionPhase.POST_LLM)
        self.setup_plan()
        self.assertEqual(await self.execute(), LevelDecision.REPLAN)
        self.assertIs(self.state.catalog.node_error(NodeId("left"), self.contracts[NodeId("left")]), error)
        self.assertEqual(self.state.gate.next_task_type, TaskType.SCENE_INIT)
        self.assertEqual(self.current(), {"right"})
        self.assertEqual(tail.calls, [])
        self.assertEqual(await self.executor.run_python_phase(self.plan, self.state, ExecutionPhase.POST_LLM, PlanRevision("plan-1")), LevelDecision.REPLAN)
        self.assertEqual(self.bindings.nodes[NodeId("root")].calls, [])

    async def test_two_identical_gates_are_conflict_and_all_signals_are_retained(self):
        async def gate(input):
            raise PythonNodeError(TestNodeError(item_id=1))
        self.node(LevelLeft, job=gate, policy=gate_policy)
        self.node(LevelRight, job=gate, policy=gate_policy)
        self.setup_plan()
        self.assertEqual(await self.execute(), LevelDecision.FAIL)
        self.assertTrue(self.state.levels[0].gate_conflict)
        self.assertEqual(len(self.state.levels[0].gates), 2)
        self.assertIsNone(self.state.gate)

    async def test_failure_and_cancel_take_priority_over_gate_without_losing_signal(self):
        for expected, exception in ((LevelDecision.FAIL, RuntimeError()), (LevelDecision.CANCEL, asyncio.CancelledError())):
            self.setUp()
            async def gate(input):
                raise PythonNodeError(TestNodeError(item_id=1))
            async def other(input):
                raise exception
            self.node(LevelLeft, job=gate, policy=gate_policy)
            self.node(LevelRight, job=other)
            self.setup_plan()
            self.assertEqual(await self.execute(), expected)
            self.assertEqual(len(self.state.levels[0].gates), 1)
            self.assertIsNone(self.state.gate)

    async def test_post_llm_gate_is_failure(self):
        async def gate(input):
            raise PythonNodeError(TestNodeError(item_id=1))
        self.node(LevelLeft, phase=ExecutionPhase.POST_LLM, job=gate, policy=gate_policy)
        self.setup_plan()
        decision = await self.executor.run_python_phase(self.plan, self.state, ExecutionPhase.POST_LLM, PlanRevision("plan-1"))
        self.assertEqual(decision, LevelDecision.FAIL)
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.FAILED)

    async def test_parent_cancellation_has_priority_over_gate_conflict(self):
        entered = self.event()
        async def blocked(input):
            entered.set()
            await asyncio.Event().wait()
        async def gate(input):
            raise PythonNodeError(TestNodeError(item_id=1))
        self.node(LevelRoot, job=blocked)
        self.node(LevelLeft, job=gate, policy=gate_policy)
        self.node(LevelRight, job=gate, policy=gate_policy)
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(entered)
        await asyncio.sleep(0)
        task.cancel()
        self.assertEqual(await task, LevelDecision.CANCEL)
        self.assertTrue(self.state.levels[0].gate_conflict)
        self.assertEqual(len(self.state.levels[0].gates), 2)

    async def test_cleanup_error_does_not_hide_parent_cancel_or_discard_peer_success(self):
        entered = self.event()
        async def blocked(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise RuntimeError("PRIVATE_CLEANUP_ERROR")
        self.node(LevelLeft, job=blocked)
        self.node(LevelRight)
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(entered)
        await asyncio.sleep(0)
        task.cancel()
        self.assertEqual(await task, LevelDecision.CANCEL)
        self.assertEqual(self.current(), {"right"})
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.FAILED)
        self.assertIsNotNone(self.state.levels[0].cancel_requested_at)
        self.assertNotIn("PRIVATE_CLEANUP_ERROR", repr(self.state.traces))

    async def test_current_results_are_reused_without_new_attempts_or_payload_trace(self):
        left = self.node(LevelLeft)
        self.setup_plan()
        await self.execute()
        before = self.state.catalog.current_outputs
        await self.execute(pass_number=1)
        self.assertEqual(left.calls, ["prepare", "execute"])
        self.assertEqual(self.state.catalog.current_outputs, before)
        self.assertEqual(self.state.levels[-1].reused_outputs, before)
        self.assertEqual(self.state.levels[-1].traces, ())

    async def test_forced_rerun_invalidates_actual_consumer_despite_skip_flag(self):
        self.node(LevelRoot)
        self.node(LevelTail, deps=("root",), reads=(required("root"),))
        self.setup_plan()
        await self.execute()
        await self.execute(pass_number=1, rerun=(NodeId("root"),))
        self.assertEqual(self.state.catalog.attempt_counters, (("root", 2), ("tail", 2)))
        self.assertEqual(self.state.levels[-1].traces[0].reads[0].result.attempt, 2)

    async def test_skip_on_replan_false_forces_new_attempt(self):
        self.node(LevelRoot, skip_on_replan=False)
        self.setup_plan()
        await self.execute()
        await self.execute(pass_number=1)
        self.assertEqual(self.state.catalog.attempt_counters, (("root", 2),))
        # Resume within the same pass must reuse this current result.
        await self.execute(pass_number=1)
        self.assertEqual(self.state.catalog.attempt_counters, (("root", 2),))

    async def test_domain_confirmation_is_required_before_reuse(self):
        async def prepare(view):
            view.record_domain_read("test.world", DomainRevision("r1"))
            return NodeInput(value=1)
        node = self.node(LevelRoot, prepare=prepare)
        self.setup_plan()
        await self.execute()
        await self.execute(confirmed_domain_revisions={"test.world": DomainRevision("r1")})
        self.assertEqual(node.calls, ["prepare", "execute"])
        await self.execute()
        self.assertEqual(self.state.catalog.attempt_counters, (("root", 2),))

    async def test_same_execution_rejects_concurrent_phase_writers(self):
        entered, release = self.event(), self.event()
        async def job(input):
            entered.set()
            await release.wait()
            return LeafOutput(value=1)
        self.node(LevelRoot, job=job)
        self.setup_plan()
        task = asyncio.create_task(self.execute())
        await self.reached(entered)
        with self.assertRaisesRegex(RuntimeError, "active phase writer"):
            await self.execute()
        release.set()
        self.assertEqual(await task, LevelDecision.CONTINUE)

    async def test_missing_executor_and_foreign_binding_fail_before_attempts_open(self):
        self.node(LevelRoot)
        self.setup_plan()
        missing = DAGExecutor(self.runner, {})
        with self.assertRaises(KeyError):
            await missing.run_python_phase(self.plan, self.state, ExecutionPhase.PRE_LLM, PlanRevision("p"))
        wrong = DAGExecutor(self.runner, {PythonNodeExecutor: FakeExecutor()})
        with self.assertRaises(TypeError):
            await wrong.run_python_phase(self.plan, self.state, ExecutionPhase.PRE_LLM, PlanRevision("p"))
        self.assertEqual(self.state.catalog.attempt_counters, ())
        foreign_registry = NodeRegistry()
        foreign_registry.register_python(LevelRoot, PythonNodeExecutor, replace(self.contracts[NodeId("root")]))
        foreign = ExecutionState(ExecutionId("other"), foreign_registry)
        with self.assertRaises(TypeError):
            await self.executor.run_python_phase(self.plan, foreign, ExecutionPhase.PRE_LLM, PlanRevision("p"))
        self.assertEqual(foreign.catalog.attempt_counters, ())

    async def test_unexpected_runner_exception_is_local_failure_and_attempt_is_closed(self):
        self.node(LevelRoot)
        self.setup_plan()
        with patch.object(self.runner, "run", side_effect=RuntimeError("PRIVATE_RUNNER_ERROR")):
            self.assertEqual(await self.execute(), LevelDecision.FAIL)
        self.assertEqual(len(self.state.catalog.closed_attempts), 1)
        self.assertNotIn("PRIVATE_RUNNER_ERROR", repr(self.state.traces))

    async def test_foreign_outcome_identity_is_rejected_and_expected_attempt_closed(self):
        self.node(LevelRoot)
        self.setup_plan()
        original = self.runner.run
        async def wrong(*args, **kwargs):
            outcome = await original(*args, **kwargs)
            return replace(outcome, identity=outcome.identity.model_copy(update={"execution_id": ExecutionId("wrong")}))
        with patch.object(self.runner, "run", side_effect=wrong):
            self.assertEqual(await self.execute(), LevelDecision.FAIL)
        self.assertEqual(self.current(), set())
        self.assertEqual(self.state.traces[0].identity.execution_id, self.state.catalog.execution_id)

    async def test_task_cancelled_outside_runner_is_normalized_and_closed(self):
        self.node(LevelRoot)
        self.setup_plan()
        with patch.object(self.runner, "run", side_effect=asyncio.CancelledError):
            self.assertEqual(await self.execute(), LevelDecision.CANCEL)
        self.assertEqual(len(self.state.catalog.closed_attempts), 1)
        self.assertEqual(self.state.traces[0].status, NodeStatus.CANCELLED)

    async def test_publication_rejects_stale_read_but_preserves_valid_sibling(self):
        self.node(LevelRoot)
        self.node(LevelLeft, deps=("root",), reads=(required("root"),))
        self.node(LevelRight, deps=("root",))
        self.setup_plan()
        original = self.runner.run
        async def stale(*args, **kwargs):
            outcome = await original(*args, **kwargs)
            if outcome.identity.node_id == NodeId("left"):
                read = outcome.reads[0]
                wrong = read.result.model_copy(update={"attempt": 9})
                return replace(outcome, reads=(read.model_copy(update={"result": wrong}),))
            return outcome
        with patch.object(self.runner, "run", side_effect=stale):
            self.assertEqual(await self.execute(), LevelDecision.FAIL)
        self.assertEqual(self.current(), {"root", "right"})
        self.assertEqual(self.state.statuses[NodeId("left")], NodeStatus.FAILED)
        self.assertEqual(len(self.state.catalog.closed_attempts), 3)

    async def test_trace_does_not_retain_payload_and_metadata_views_are_read_only(self):
        references = []
        async def job(input):
            output = LeafOutput(value=9)
            references.append(weakref.ref(output))
            return output
        self.node(LevelRoot, job=job)
        self.setup_plan()
        await self.execute()
        self.state.catalog.begin_attempt(NodeId("root"), PlanRevision("new"))
        # Let asyncio release the completed gather/shield callbacks; retained
        # execution metadata must not own their payload after that cleanup.
        await asyncio.sleep(0)
        gc.collect()
        self.assertIsNone(references[0]())
        with self.assertRaises(TypeError):
            self.state.statuses[NodeId("root")] = NodeStatus.IDLE
        with self.assertRaises(FrozenInstanceError):
            self.state.traces[0].status = NodeStatus.FAILED
        for name in ("output", "error", "validation"):
            self.assertFalse(hasattr(self.state.traces[0], name))

    async def test_empty_phase_is_continue_and_has_no_attempts(self):
        self.setup_plan()
        self.assertEqual(await self.execute(), LevelDecision.CONTINUE)
        self.assertEqual(self.state.levels, ())
        self.assertEqual(self.state.catalog.attempt_counters, ())


class LevelImportTests(unittest.TestCase):
    def test_target_import_does_not_load_legacy_nodes(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run([sys.executable, "-c", "import sys,json; from app.application.engine.runtime.dag.dagExecutor import DAGExecutor; print(json.dumps([n for n in sys.modules if n == 'app.application.engine.nodes' or n.startswith('app.application.engine.nodes.')]))"],
                                cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "backend")), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
