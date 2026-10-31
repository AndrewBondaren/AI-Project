"""A3.6: typed hooks, pass bounds, snapshot lifecycle and exact resume stage."""

import asyncio
from dataclasses import replace
import gc
import logging
from typing import Never
import unittest
from unittest.mock import patch
import weakref

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import PassStage, ResolveResult
from app.application.engine.diagnostics.dagLog import emit
from app.application.engine.diagnostics.events import LifecycleDiagnostic
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import ExecutionEventCode, ExecutionSeverity
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from tests.dag_typing.execution import test_level as levels
from tests.dag_typing.fixtures import CompositeOutput, GraphRuleState, LeafOutput, NodeInput, TestNodeError
from tests.dag_typing.llm import test_group as groups
from tests.dag_typing.lifecycle import test_restore as restore_tests


class Hooks:
    consumer = NodeId("lifecycle-hooks")
    response_type = LeafOutput

    def __init__(self, compiler, reads):
        self.compiler, self.reads = compiler, reads
        self.compiles, self.transitions, self.effects = [], [], []
        self.resolve_calls = 0
        self.next_tasks = []
        self.effects_action = None
        self.response_action = None
        self.transition_action = None
        self.revision_override = None

    def compile(self, task_type, pass_number):
        self.compiles.append((task_type, pass_number))
        return self.revision_override or PlanRevision(f"revision-{pass_number}"), self.compiler.compile(GraphRuleState(task_type=task_type))

    def transition(self, view):
        self.transitions.append(1)
        if self.transition_action:
            return self.transition_action(view)
        return self.next_tasks.pop(0) if self.next_tasks else None

    async def apply_effects(self, view):
        self.effects.append(view.require(self.reads[-1]).value)
        if self.effects_action:
            await self.effects_action(view)

    def resolve(self, view):
        self.resolve_calls += 1
        if self.response_action:
            return self.response_action(view)
        return ResolveResult(ok=True, data=view.require(self.reads[-1]))


class PassTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group = groups.GroupTests()
        self.group.setUp()
        self.python = levels.LevelTests()
        self.python.setUp()
        self.python.registry = self.group.registry
        self.python.bindings = self.group.bindings
        self.store = SnapshotStore[Never]()
        self.service = ExecutionSnapshotService[Never]()
        self.events = []
        self.execution_id = ExecutionId("passes")
        self.max_passes = 3

    def setup_engine(self, request, *, pre_job=None, post_job=None, pre_prepare=None, gate=False, empty=False):
        if not empty:
            self.pre = self.python.node(levels.LevelRoot, job=pre_job, prepare=pre_prepare,
                                         policy=levels.gate_policy if gate else None)
            required = levels.required("root")
            async def prepare(view):
                return NodeInput(value=view.require(required).value)
            self.llm = self.group.node(groups.First, deps=(levels.LevelRoot.id,), reads=(required,), prepare=prepare)
            self.post = self.python.node(levels.LevelTail, phase=ExecutionPhase.POST_LLM, deps=(groups.First.id,),
                                          reads=(levels.required(groups.First.id),), job=post_job)
            reads = (required, levels.required(groups.First.id), levels.required(levels.LevelTail.id))
        else:
            reads = ()
        compiler = GraphCompiler(self.group.registry, self.group.bindings, compile_rules=lambda rules: (), evaluate_rules=lambda node, state: True)
        compiler.precompile()
        self.hooks = Hooks(compiler, reads)
        executor = DAGExecutor(self.python.runner, {PythonNodeExecutor: PythonNodeExecutor()}, emit=lambda event: None)
        self.engine = LLMExecutionEngine(executor, self.group.aggregate, self.group.registry, self.hooks,
                                         request, self.service, self.store, emit=self.events.append)

    async def run_engine(self, **kwargs):
        return await self.engine.run(self.execution_id, TaskType.INTENT_DETECTION, max_passes=self.max_passes,
                                     options=self.group.options, **kwargs)

    async def resume(self, **kwargs):
        return await self.engine.resume(self.execution_id, max_passes=self.max_passes, options=self.group.options, **kwargs)

    async def test_pre_llm_post_effects_response_flow_and_typed_response_identity(self):
        request = groups.Request([groups.response(first=7)])
        self.setup_engine(request)
        result = await self.run_engine()
        self.assertIsInstance(result.data, LeafOutput)
        self.assertEqual(result.data.value, 8)
        self.assertEqual(self.pre.calls, ["prepare", "execute"])
        self.assertEqual(self.post.calls, ["prepare", "execute"])
        self.assertEqual(self.hooks.effects, [8])
        self.assertEqual(self.hooks.resolve_calls, 1)
        self.assertIsNone(self.store.load(self.execution_id))
        self.assertEqual(self.events, [])

    async def test_transition_is_delegated_and_effects_wait_for_final_pass(self):
        request = groups.Request([groups.response(first=1), groups.response(first=2)])
        self.setup_engine(request)
        self.hooks.next_tasks = [TaskType.SCENE_INIT, None]
        result = await self.run_engine()
        self.assertEqual(result.data.value, 3)
        self.assertEqual(self.hooks.compiles, [(TaskType.INTENT_DETECTION, 0), (TaskType.SCENE_INIT, 1)])
        self.assertEqual(self.hooks.effects, [3])
        self.assertEqual(len(request.calls), 2)

    async def test_pre_gate_skips_llm_post_and_uses_declared_target(self):
        calls = []
        async def gate(input):
            calls.append(1)
            if len(calls) == 1:
                raise PythonNodeError(TestNodeError(item_id=1))
            return LeafOutput(value=1)
        request = groups.Request([groups.response(first=2)])
        self.setup_engine(request, pre_job=gate, gate=True)
        result = await self.run_engine()
        self.assertEqual(result.data.value, 3)
        self.assertEqual(self.hooks.compiles[1], (TaskType.SCENE_INIT, 1))
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.hooks.transitions, [1])
        self.assertEqual(self.hooks.effects, [3])

    async def test_total_pass_limit_is_enforced_before_effects(self):
        self.setup_engine(groups.Request([groups.response(first=1)]))
        self.max_passes = 1
        self.hooks.next_tasks = [TaskType.SCENE_INIT]
        with self.assertRaisesRegex(RuntimeError, "pass limit"):
            await self.run_engine()
        self.assertEqual(self.hooks.effects, [])
        self.assertEqual(self.hooks.resolve_calls, 0)
        self.assertIsNone(self.store.load(self.execution_id))

    async def test_cancelled_pre_resumes_pre_then_remaining_phases(self):
        calls = []
        async def cancel_once(input):
            calls.append(1)
            if len(calls) == 1:
                raise asyncio.CancelledError
            return LeafOutput(value=1)
        request = groups.Request([groups.response(first=2)])
        self.setup_engine(request, pre_job=cancel_once)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        self.assertEqual(snapshot.cursor.stage, PassStage.PRE_LLM)
        self.assertEqual(request.calls, [])
        self.assertEqual((await self.resume()).data.value, 3)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(self.store.load(self.execution_id))

    async def test_cancelled_llm_resumes_same_pass_without_repeating_pre(self):
        request = groups.Request([asyncio.CancelledError(), groups.response(first=2)])
        self.setup_engine(request)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        self.assertEqual(snapshot.cursor.stage, PassStage.LLM)
        self.assertEqual(snapshot.metadata.pass_number, 0)
        self.assertEqual(snapshot.cursor.task_type, TaskType.INTENT_DETECTION)
        result = await self.resume()
        self.assertEqual(result.data.value, 3)
        self.assertEqual(self.pre.calls, ["prepare", "execute"])
        self.assertEqual(len(request.calls), 2)
        self.assertEqual(self.events[0].code, ExecutionEventCode.SNAPSHOT_SAVED)

    async def test_cancelled_post_resumes_post_without_repeating_current_llm_group(self):
        calls = []
        async def cancel_once(input):
            calls.append(1)
            if len(calls) == 1:
                raise asyncio.CancelledError
            return LeafOutput(value=input.value)
        request = groups.Request([groups.response(first=3)])
        self.setup_engine(request, post_job=cancel_once)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        self.assertEqual(self.store.load(self.execution_id).cursor.stage, PassStage.POST_LLM)
        self.assertEqual((await self.resume()).data.value, 4)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.pre.calls, ["prepare", "execute"])
        self.assertEqual(len(calls), 2)

    async def test_effects_retry_is_delegated_without_reexecuting_nodes(self):
        request = groups.Request([groups.response(first=4)])
        self.setup_engine(request)
        async def cancel_once(view):
            if len(self.hooks.effects) == 1:
                raise asyncio.CancelledError
        self.hooks.effects_action = cancel_once
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        self.assertEqual(self.store.load(self.execution_id).cursor.stage, PassStage.EFFECTS)
        self.assertEqual((await self.resume()).data.value, 5)
        self.assertEqual(self.hooks.effects, [5, 5])
        self.assertEqual(len(request.calls), 1)

    async def test_response_resume_does_not_repeat_completed_effects(self):
        request = groups.Request([groups.response(first=4)])
        self.setup_engine(request)
        def response(view):
            if self.hooks.resolve_calls == 1:
                asyncio.current_task().cancel()
            return ResolveResult(ok=True, data=view.require(self.hooks.reads[-1]))
        self.hooks.response_action = response
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.create_task(self.run_engine())
        self.assertEqual(self.store.load(self.execution_id).cursor.stage, PassStage.RESPONSE)
        self.assertEqual((await self.resume()).data.value, 5)
        self.assertEqual(self.hooks.effects, [5])
        self.assertEqual(len(request.calls), 1)

    async def test_fresh_domain_reads_survive_between_phases_without_external_confirmation(self):
        async def prepare(view):
            view.record_domain_read("world", DomainRevision("r1"))
            return NodeInput(value=3)
        request = groups.Request([groups.response(first=4)])
        self.setup_engine(request, pre_prepare=prepare)
        self.assertEqual((await self.run_engine()).data.value, 5)
        self.assertEqual(len(request.calls), 1)

    async def test_unconfirmed_resume_rewinds_missing_producers_and_recomputes_dependents(self):
        async def prepare(view):
            view.record_domain_read("world", DomainRevision("r1"))
            return NodeInput(value=3)
        request = groups.Request([asyncio.CancelledError(), groups.response(first=4)])
        self.setup_engine(request, pre_prepare=prepare)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        await self.resume()
        self.assertEqual(self.pre.calls, ["prepare", "execute", "prepare", "execute"])
        self.assertEqual(len(request.calls), 2)

    async def test_confirmed_domain_revision_reuses_pre_on_resume(self):
        async def prepare(view):
            view.record_domain_read("world", DomainRevision("r1"))
            return NodeInput(value=3)
        request = groups.Request([asyncio.CancelledError(), groups.response(first=4)])
        self.setup_engine(request, pre_prepare=prepare)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        await self.resume(confirmed_domain_revisions={"world": DomainRevision("r1")})
        self.assertEqual(self.pre.calls, ["prepare", "execute"])

    async def test_restore_version_or_revision_failure_preserves_original_snapshot(self):
        request = groups.Request([asyncio.CancelledError()])
        self.setup_engine(request)
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        bad = replace(snapshot, metadata=snapshot.metadata.model_copy(update={"format_version": 999}))
        self.store.save(bad)
        with self.assertRaisesRegex(ValueError, "format version"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), bad)
        self.store.save(snapshot)
        self.hooks.revision_override = PlanRevision("changed")
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.events[-1].code, ExecutionEventCode.RESTORE_FAILED)

    async def test_missing_cursor_is_rejected_without_guessing_from_trace(self):
        self.setup_engine(groups.Request([asyncio.CancelledError()]))
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = replace(self.store.load(self.execution_id), cursor=None)
        self.store.save(snapshot)
        with self.assertRaisesRegex(ValueError, "cursor"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)

    async def test_save_failure_is_explicit_and_does_not_emit_saved(self):
        self.setup_engine(groups.Request([asyncio.CancelledError()]))
        with patch.object(self.store, "save", side_effect=OSError("store unavailable")):
            with self.assertRaisesRegex(OSError, "store unavailable"):
                await self.run_engine()
        self.assertEqual([event.code for event in self.events], [ExecutionEventCode.SNAPSHOT_FAILED])
        self.assertIsNone(self.store.load(self.execution_id))

    async def test_callback_cannot_read_undeclared_output(self):
        self.setup_engine(groups.Request([groups.response(first=1)]))
        self.hooks.reads = self.hooks.reads[:1]
        self.hooks.transition_action = lambda view: view.require(levels.required(groups.First.id))
        with self.assertRaises(PermissionError):
            await self.run_engine()
        self.assertEqual(self.hooks.effects, [])

    async def test_response_pojo_mismatch_is_rejected_and_failure_reply_is_delegated(self):
        self.setup_engine(groups.Request([groups.response(first=1), groups.response(first=1)]))
        self.hooks.response_action = lambda view: ResolveResult(ok=True, data=CompositeOutput(leaves=()))
        with self.assertRaisesRegex(TypeError, "response"):
            await self.run_engine()
        self.hooks.response_action = lambda view: ResolveResult(ok=False, error="integration response")
        self.assertEqual((await self.run_engine()).error, "integration response")

    async def test_raw_response_envelope_cannot_cross_typed_boundary(self):
        self.setup_engine(groups.Request([groups.response(first=1)]))
        self.hooks.response_action = lambda view: {"ok": True, "data": {"value": 1}}
        with self.assertRaisesRegex(TypeError, "ResolveResult"):
            await self.run_engine()

    async def test_failed_phase_prevents_effects_and_response(self):
        self.setup_engine(groups.Request([RuntimeError("request failed")]))
        with self.assertRaisesRegex(RuntimeError, "pass failed"):
            await self.run_engine()
        self.assertEqual(self.hooks.effects, [])
        self.assertEqual(self.hooks.resolve_calls, 0)

    async def test_state_release_runs_on_success_failure_and_cancellation(self):
        self.setup_engine(groups.Request([groups.response(first=1), RuntimeError("failure"), asyncio.CancelledError()]))
        released = []
        original = ExecutionState.release
        def release(state):
            original(state)
            released.append(state)
        with patch.object(ExecutionState, "release", release):
            await self.run_engine()
            with self.assertRaises(RuntimeError):
                await self.run_engine()
            with self.assertRaises(asyncio.CancelledError):
                await self.run_engine()
        self.assertEqual(len(released), 3)
        self.assertTrue(all(state.is_released and not state.catalog.current_outputs for state in released))
        self.assertIsNotNone(self.store.load(self.execution_id))

    async def test_max_passes_is_total_on_resume_and_fresh_run_cannot_replace_snapshot(self):
        self.setup_engine(groups.Request([asyncio.CancelledError()]))
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        with self.assertRaisesRegex(ValueError, "requires resume"):
            await self.run_engine()
        self.max_passes = 0
        with self.assertRaises(ValueError):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)

    async def test_resume_cannot_reset_total_pass_budget(self):
        request = groups.Request([groups.response(first=1), asyncio.CancelledError(), groups.response(first=2)])
        self.setup_engine(request)
        self.hooks.next_tasks = [TaskType.SCENE_INIT]
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        self.assertEqual(snapshot.metadata.pass_number, 1)
        self.assertEqual(snapshot.cursor.task_type, TaskType.SCENE_INIT)
        self.max_passes = 1
        with self.assertRaisesRegex(ValueError, "pass"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)
        self.assertEqual(len(request.calls), 2)
        self.max_passes = 2
        self.assertEqual((await self.resume()).data.value, 3)

    async def test_extension_restores_request_state_before_plan_and_effects_callbacks(self):
        calls = []
        extension = restore_tests.Extension(calls)
        self.store = SnapshotStore[LeafOutput]()
        self.service = ExecutionSnapshotService(extension)
        self.setup_engine(groups.Request([asyncio.CancelledError(), groups.response(first=2)]))
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        compile_plan = self.hooks.compile
        def compile_after_restore(task_type, pass_number):
            self.assertEqual([name for name, _ in calls], ["validate extension", "restore extension"])
            return compile_plan(task_type, pass_number)
        self.hooks.compile = compile_after_restore
        self.assertTrue((await self.resume()).ok)

    async def test_capture_failure_preserves_previous_resume_snapshot(self):
        calls = []
        extension = restore_tests.Extension(calls)
        self.store = SnapshotStore[LeafOutput]()
        self.service = ExecutionSnapshotService(extension)
        self.setup_engine(groups.Request([groups.response(first=2)]))
        async def cancel(view):
            raise asyncio.CancelledError
        self.hooks.effects_action = cancel
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        extension.value = {"invalid": "extension"}
        with self.assertRaisesRegex(TypeError, "extension"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)
        self.assertEqual(self.events[-1].code, ExecutionEventCode.SNAPSHOT_FAILED)

    async def test_failed_resume_effect_callback_preserves_original_snapshot(self):
        self.setup_engine(groups.Request([groups.response(first=2)]))
        async def effect(view):
            if len(self.hooks.effects) == 1:
                raise asyncio.CancelledError
            raise RuntimeError("domain effect rejected")
        self.hooks.effects_action = effect
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        snapshot = self.store.load(self.execution_id)
        with self.assertRaisesRegex(RuntimeError, "domain effect rejected"):
            await self.resume()
        self.assertIs(self.store.load(self.execution_id), snapshot)

    async def test_empty_graph_can_save_lifecycle_without_synthetic_node_identity(self):
        self.setup_engine(groups.Request([]), empty=True)
        async def cancel(view):
            raise asyncio.CancelledError
        self.hooks.apply_effects = cancel
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        event = self.events[-1]
        self.assertEqual(event.execution_id, self.execution_id)
        self.assertNotIn("identity", event.model_dump())
        self.assertEqual(self.store.load(self.execution_id).catalog.closed_attempts, ())

    async def test_same_execution_cannot_run_concurrently(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def request():
            entered.set()
            await release.wait()
            return groups.response(first=1)
        self.setup_engine(groups.Request([request]))
        task = asyncio.create_task(self.run_engine())
        await asyncio.wait_for(entered.wait(), 3)
        with self.assertRaisesRegex(RuntimeError, "already running"):
            await self.run_engine()
        release.set()
        self.assertTrue((await task).ok)

    async def test_saved_output_is_kept_by_store_then_freed_after_terminal_success(self):
        references = []
        async def post(input):
            output = LeafOutput(value=input.value)
            references.append(weakref.ref(output))
            return output
        self.setup_engine(groups.Request([groups.response(first=1)]), post_job=post)
        async def cancel(view):
            raise asyncio.CancelledError
        self.hooks.effects_action = cancel
        with self.assertRaises(asyncio.CancelledError):
            await self.run_engine()
        await asyncio.sleep(0)
        gc.collect()
        self.assertIsNotNone(references[0]())
        self.hooks.effects_action = None
        self.hooks.response_action = lambda view: ResolveResult(ok=True, data=LeafOutput(value=99))
        await self.resume()
        await asyncio.sleep(0)
        gc.collect()
        self.assertIsNone(references[0]())


class LifecycleLogTests(unittest.TestCase):
    def test_existing_emitter_strips_unknown_lifecycle_subclass_payload(self):
        class Secret(LifecycleDiagnostic):
            secret: str
        event = Secret(execution_id=ExecutionId("empty"), plan_revision=PlanRevision("r1"), pass_number=0,
                       stage=PassStage.EFFECTS, code=ExecutionEventCode.SNAPSHOT_SAVED, severity=ExecutionSeverity.INFO,
                       timestamp=1.0, status=NodeStatus.CANCELLED, message="saved", secret="PRIVATE")
        records = []
        with patch.object(logging.getLogger("app.engine.dag"), "log", side_effect=lambda *args, **kwargs: records.append(kwargs)):
            emit(event)
        self.assertNotIn("PRIVATE", str(records))
        self.assertNotIn("identity", records[0]["extra"]["event"])
