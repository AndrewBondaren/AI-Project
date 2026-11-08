import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.executionBindings import ResolveResult
from app.application.engine.contracts.outputRef import OutputRef, RequiredOutput
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dagEngine import DAGEngine
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.taskType import TaskType
from app.application.engine.contracts.invocation.callTarget import CallTarget
from app.application.engine.contracts.invocation.continuationContract import ContinuationContract
from app.application.engine.contracts.invocation.executionStore import CloseReceipt, OwnershipConflict, RestoreFailure
from app.application.engine.contracts.invocation.nodeStep import Call, CallGroup, CallRequest, Complete
from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallFailure, CallSuccess
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractVersion, ExecutionId, NodeId, PlanRevision
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.ownedExecution import ExecutionStopping
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome, InvocationGraph
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from tests.dag_typing.fixtures import TestNodeError, FakeExecutor, GraphBindings, GraphRuleState


class Payload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Count(Payload):
    value: int


class Text(Payload):
    text: str


class PipelineState(Payload):
    waiting_for: Literal["count", "format"]


class TransformRequest(Payload):
    operation: Literal["count", "format"]
    value: str


class TransformResult(RootModel[Count | Text]):
    model_config = ConfigDict(frozen=True)


def target(name, input_type, output_type):
    return CallTarget(NodeId(name), ContractId(name), ContractVersion("1"), input_type, output_type,
                      (TestNodeError,) if name == "transform" else ())


TRANSFORM = target("transform", TransformRequest, TransformResult)
COUNT = target("count", Payload, Count)
FORMAT = target("format", Count, Text)
KEY = CallKey("transform")


@dataclass(frozen=True, kw_only=True)
class Transform(PythonNode[TransformRequest, TransformResult, TestNodeError]):
    id: NodeId = TRANSFORM.node_id

    async def prepare_input(self, view):
        raise AssertionError("called target requires explicit input")

    async def execute(self, input):
        if input.value == "failed":
            raise PythonNodeError(TestNodeError(item_id=1))
        if input.value == "cancelled":
            raise asyncio.CancelledError
        if input.operation == "count":
            return TransformResult(Count(value=len(input.value)))
        return TransformResult(Text(text=f"count={input.value}"))


class Workflow(ResumablePythonNode):
    async def prepare_input(self, view):
        return Payload()


@dataclass(frozen=True, kw_only=True)
class CountCaller(Workflow):
    id: NodeId = COUNT.node_id

    async def start(self, input):
        return Call(KEY, TRANSFORM, TransformRequest(operation="count", value="hello"), input)

    async def resume(self, state, event):
        result = event.get(KEY, TRANSFORM)
        assert isinstance(result, CallSuccess) and isinstance(result.output.root, Count)
        return Complete(result.output.root)


@dataclass(frozen=True, kw_only=True)
class FormatCaller(Workflow):
    id: NodeId = FORMAT.node_id

    async def start(self, input):
        return Call(KEY, TRANSFORM, TransformRequest(operation="format", value=str(input.value)), Payload())

    async def resume(self, state, event):
        result = event.get(KEY, TRANSFORM)
        assert isinstance(result, CallSuccess) and isinstance(result.output.root, Text)
        return Complete(result.output.root)


@dataclass(frozen=True, kw_only=True)
class Pipeline(Workflow):
    id: NodeId = NodeId("pipeline")

    async def start(self, input):
        return Call(CallKey("count"), COUNT, input, PipelineState(waiting_for="count"))

    async def resume(self, state, event):
        if state.waiting_for == "count":
            result = event.get(CallKey("count"), COUNT)
            assert isinstance(result, CallSuccess)
            return Call(CallKey("format"), FORMAT, result.output, PipelineState(waiting_for="format"))
        result = event.get(CallKey("format"), FORMAT)
        assert isinstance(result, CallSuccess)
        return Complete(result.output)


@dataclass(frozen=True, kw_only=True)
class Group(Pipeline):
    async def start(self, input):
        return CallGroup(tuple(CallRequest(CallKey(name), TRANSFORM, TransformRequest(operation="count", value=name))
                               for name in ("failed", "cancelled", "ok")), Payload())

    async def resume(self, state, event):
        assert isinstance(event.get(CallKey("failed"), TRANSFORM), CallFailure)
        assert isinstance(event.get(CallKey("cancelled"), TRANSFORM), CallCancelled)
        assert isinstance(event.get(CallKey("ok"), TRANSFORM), CallSuccess)
        return Complete(Text(text="joined"))


@dataclass(frozen=True, kw_only=True)
class Source(PythonNode[Payload, Payload, Never]):
    id: NodeId = NodeId("source")

    async def prepare_input(self, view):
        return Payload()

    async def execute(self, input):
        return input


@dataclass(frozen=True, kw_only=True)
class Left(Source):
    id: NodeId = NodeId("left")


@dataclass(frozen=True, kw_only=True)
class Right(Source):
    id: NodeId = NodeId("right")


@dataclass(frozen=True, kw_only=True)
class Merge(Source):
    id: NodeId = NodeId("merge")

    async def prepare_input(self, view):
        for node in (Left.id, Right.id):
            view.require(RequiredOutput(OutputRef(node, Payload)))
        return Payload()


def runtime(entry=Pipeline, store=None, transform=Transform, retry_policy=None, diamond=False, counter=CountCaller, lease_seconds=300,
            interaction=None, counter_wait=None, entry_lifecycle=None, enable_stop_intent=False, pack_closer=None,
            workers=1):
    registry, bindings = NodeRegistry(), GraphBindings()
    if diamond:
        for cls, deps in ((Source, ()), (Left, (Source.id,)), (Right, (Source.id,)), (Merge, (Left.id, Right.id))):
            reads = tuple(RequiredOutput(OutputRef(n, Payload)) for n in deps) if cls is Merge else ()
            contract = NodeContract(Payload, Payload, ContractId(cls.id), ContractVersion("1"), reads, error_types=())
            registry.register_python(cls, FakeExecutor, contract)
            bindings.nodes[cls.id] = cls(deps=deps)
    for cls, declaration, calls in (
        (entry, target(entry.id, Payload, Text), (TRANSFORM,) if entry is Group else (COUNT, FORMAT)),
        (counter, COUNT, (TRANSFORM,)), (FormatCaller, FORMAT, (TRANSFORM,)), (transform, TRANSFORM, ()),
    ):
        state_type = PipelineState if cls is Pipeline else Payload
        continuation = ContinuationContract(ContractId(f"{cls.id}.state"), ContractVersion("1"), state_type) if calls else None
        contract = NodeContract(declaration.input_type, declaration.output_type, declaration.contract_id,
                                declaration.version, (), calls=calls, continuation=continuation, error_types=declaration.error_types,
                                retry_policy=retry_policy if cls is transform else None,
                                input_wait=counter_wait if cls is counter else None,
                                lifecycle=entry_lifecycle if cls is entry else None)
        register = registry.register_resumable if calls else registry.register_python
        register(cls, FakeExecutor, contract)
        bindings.nodes[cls.id] = cls(deps=(Merge.id,)) if diamond and cls is transform else cls()
    compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
    compiler.precompile()
    config = InvocationOptions(store, workers=workers, invocation_limit=16, lease_seconds=lease_seconds, interaction=interaction) if store else None
    executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {FakeExecutor: FakeExecutor()},
                           invocation_options=config)
    plan = compiler.compile(GraphRuleState(), invocation_root=entry.id)
    if store is not None:
        return DAGEngine(executor, None, registry, PipelineHooks(plan), None, ExecutionSnapshotService(), SnapshotStore(),
                         enable_stop_intent=enable_stop_intent, pack_closer=pack_closer)
    return executor, plan


class PipelineHooks:
    consumer = NodeId("result")
    reads = (RequiredOutput(OutputRef(Pipeline.id, Text)),)
    response_type = Text

    def __init__(self, plan):
        self.plan = plan

    def compile(self, task_type, pass_number):
        return PlanRevision("1"), self.plan

    def transition(self, view):
        return None

    async def apply_effects(self, view):
        pass

    def resolve(self, view):
        return ResolveResult(True, view.require(self.reads[0]))


class Crash(Exception):
    pass


class InterruptedStore(SQLiteExecutionStore):
    stop_at = 0
    crashed = False

    async def release(self, claim):
        if not self.crashed:
            await super().release(claim)

    async def checkpoint(self, *args):
        revision = await super().checkpoint(*args)
        if revision == self.stop_at:
            self.crashed = True
            raise Crash
        return revision


class CompilerTests(unittest.TestCase):
    def test_declared_target_must_match_registry_and_phase(self):
        from dataclasses import replace
        from app.dataModel.engine.dag.executionPhase import ExecutionPhase
        for kind in ("version", "cross-phase", "mixed-cycle", "unknown"):
            with self.subTest(kind=kind):
                registry, bindings = NodeRegistry(), GraphBindings()
                declared = replace(TRANSFORM, version=ContractVersion("2")) if kind == "version" else TRANSFORM
                calls = (replace(declared, node_id=NodeId("unknown")),) if kind == "unknown" else (declared,)
                continuation = ContinuationContract(ContractId("count.state"), ContractVersion("1"), Payload)
                registry.register_resumable(CountCaller, FakeExecutor, NodeContract(Payload, Count, COUNT.contract_id,
                    COUNT.version, (), error_types=(), calls=calls, continuation=continuation))
                registry.register_python(Transform, FakeExecutor, NodeContract(TransformRequest, TransformResult, TRANSFORM.contract_id,
                    TRANSFORM.version, (), error_types=TRANSFORM.error_types))
                bindings.nodes[CountCaller.id] = CountCaller()
                bindings.nodes[Transform.id] = Transform(deps=(CountCaller.id,) if kind == "mixed-cycle" else (),
                    phase=ExecutionPhase.POST_LLM if kind == "cross-phase" else ExecutionPhase.PRE_LLM)
                compiler = GraphCompiler(registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
                with self.assertRaises((ValueError, TypeError)):
                    compiler.precompile()

    def test_bad_group_and_incompatible_restore(self):
        from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
        from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        request = TRANSFORM.request(KEY, TransformRequest(operation="count", value="hello"))
        for requests in ((), (request, request)):
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                CallGroup(requests, Payload())
        _, plan = runtime()
        coordinator = InvocationCoordinator.create(plan, ExecutionId("restore"), PlanRevision("1"), Pipeline.id, 5, None)
        coordinator.graph.records[coordinator.graph.root].version = ContractVersion("unknown")
        with self.assertRaises(RestoreFailure):
            CheckpointCodec.decode(CheckpointCodec.encode(coordinator.graph), plan)


class FailOnceTransform(Transform):
    async def execute(self, input):
        if input.operation == "count" and not getattr(self, "attempted", False):
            object.__setattr__(self, "attempted", True)
            raise PythonNodeError(TestNodeError(item_id=1))
        return await super().execute(input)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_cancellation_drains_child_then_releases_claim(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        from app.application.engine.runtime.invocations.recovery.executionRecovery import ExecutionRecovery

        store = MemoryExecutionStore()
        engine = runtime(store=store)
        key = ExecutionId("repeated-cancel")
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)
        started, draining, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
        cleanup = []

        async def worker(*args):
            started.set()
            try:
                await asyncio.Future()
            finally:
                draining.set()
                await finish.wait()
                cleanup.append("drained")

        release = store.release
        async def record_release(claim):
            await release(claim)
            cleanup.append("released")

        with patch.object(ExecutionRecovery, "_resume_claimed", worker), patch.object(store, "release", record_release):
            parent = asyncio.create_task(engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options))
            try:
                await asyncio.wait_for(started.wait(), 5)
                parent.cancel()
                await asyncio.wait_for(draining.wait(), 5)
                parent.cancel()
                await asyncio.sleep(0)
            finally:
                finish.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(parent, 5)
        self.assertEqual(cleanup, ["drained", "released"])
        self.assertTrue((await engine.resume(key, max_passes=1, options=options)).ok)

    async def test_failed_durable_create_releases_state_and_allows_retry(self):
        from app.application.engine.runtime.dag.executionState import ExecutionState
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore

        store = MemoryExecutionStore()
        engine = runtime(store=store)
        key = ExecutionId("retry-create")
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)
        with (patch.object(store, "create", side_effect=OSError("create failed")),
              patch.object(ExecutionState, "release", autospec=True, side_effect=ExecutionState.release) as release):
            with self.assertRaisesRegex(OSError, "create failed"):
                await engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
            release.assert_called_once()
            self.assertTrue(release.call_args.args[0].is_released)
        with self.assertRaises(KeyError):
            await store.load(key)
        result = await engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
        self.assertTrue(result.ok)

    async def test_stop_fences_selected_child_retry_and_join(self):
        schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
        for name, target_node, step, attempt in (("child", COUNT.node_id, 0, 1),
                                                 ("retry", TRANSFORM.node_id, 0, 2),
                                                 ("join", COUNT.node_id, 1, 2)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "race.sqlite"
                with closing(sqlite3.connect(path)) as first, closing(sqlite3.connect(path)) as second:
                    first.executescript(schema.read_text("utf-8"))
                    old, new = SQLiteExecutionStore(first), SQLiteExecutionStore(second)
                    executor, plan = runtime(transform=FailOnceTransform, retry_policy=lambda _, n: n == 1)
                    selected, resume = asyncio.Event(), asyncio.Event()
                    stale = []
                    starts = []
                    start, dispatch = executor._start_selected, executor._invocation_step

                    async def barrier(coordinator, owned, record):
                        if (record.node_id, record.step_index, record.attempt_counter) == (target_node, step, attempt):
                            stale.append(owned.claim)
                            selected.set()
                            await resume.wait()
                        return await start(coordinator, owned, record)

                    async def count(coordinator, record):
                        if resume.is_set():
                            starts.append(record.identity())
                        return await dispatch(coordinator, record)

                    key = ExecutionId(name)
                    args = (plan, key, Pipeline.id, PlanRevision("1"))
                    with patch.object(executor, "_start_selected", barrier), patch.object(executor, "_invocation_step", count):
                        task = asyncio.create_task(executor.run_invocation(*args, old, owner="old", workers=1, invocation_limit=16))
                        try:
                            await asyncio.wait_for(selected.wait(), 10)
                            with second:
                                second.execute("UPDATE dag_executions SET lease_until=0 WHERE execution_id=?", (key,))
                            claim = await new.claim(key, "recovery", 60)
                            before = await new.load(key)
                            await new.record_stop_intent(claim, before.revision, FailedOutcome(diagnostic="execution stopped"))
                            with self.assertRaises(OwnershipConflict):
                                await old.checkpoint(stale[0], before.revision + 1, before.status, before.blob)
                            await new.release(claim)
                            with patch.object(old, "claim", side_effect=AssertionError("ordinary claim after intent")):
                                with self.assertRaises(OwnershipConflict):
                                    await executor.run_invocation(*args, old, owner="direct", workers=1, invocation_limit=16)
                            resume.set()
                            with self.assertRaises(OwnershipConflict):
                                await task
                            self.assertEqual(starts, [])
                        finally:
                            resume.set()
                            task.cancel()
                            await asyncio.gather(task, return_exceptions=True)

    async def test_stop_revokes_running_sibling_and_drains_cleanup(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        key = ExecutionId("admitted")
        executor, plan = runtime(Group)
        admitted, cleaned = asyncio.Event(), asyncio.Event()
        selected, proceed = asyncio.Event(), asyncio.Event()
        original_step, original_start = executor._invocation_step, executor._start_selected
        starts_after_stop = []

        async def running(coordinator, record):
            if proceed.is_set():
                starts_after_stop.append(record.identity())
            if record.call_key == "failed":
                admitted.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
            return await original_step(coordinator, record)

        async def selected_sibling(coordinator, owned, record):
            if record.call_key == "cancelled":
                selected.set()
                await proceed.wait()
            return await original_start(coordinator, owned, record)

        with patch.object(executor, "_invocation_step", running), patch.object(executor, "_start_selected", selected_sibling):
            task = asyncio.create_task(executor.run_invocation(plan, key, Group.id, PlanRevision("1"), store,
                                                              owner="old", workers=2, invocation_limit=8))
            try:
                await asyncio.wait_for(asyncio.gather(admitted.wait(), selected.wait()), 5)
                store._entries[key].lease_until = 0
                claim = await store.claim(key, "new", 60)
                intent = await store.record_stop_intent(claim, (await store.load(key)).revision,
                                                        FailedOutcome(diagnostic="stop siblings"))
                proceed.set()
                with self.assertRaises(OwnershipConflict):
                    await task
                self.assertTrue(cleaned.is_set())
                self.assertEqual(starts_after_stop, [])
                self.assertEqual((await store.load(key)).stop_intent, intent)
            finally:
                proceed.set()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_stop_fences_next_pass_before_compile(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        engine = runtime(store=store, enable_stop_intent=True)
        selected, proceed = asyncio.Event(), asyncio.Event()
        transition = False
        key = ExecutionId("next-pass")
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)

        def choose_pass(self, view):
            nonlocal transition
            transition = True
            return TaskType.INTENT_DETECTION

        checkpoint = store.checkpoint
        async def barrier(claim, revision, status, blob):
            if transition:
                selected.set()
                await proceed.wait()
            return await checkpoint(claim, revision, status, blob)

        with (patch.object(PipelineHooks, "transition", choose_pass), patch.object(store, "checkpoint", barrier),
              patch.object(PipelineHooks, "compile", autospec=True, side_effect=PipelineHooks.compile) as compile_plan):
            task = asyncio.create_task(engine.run(key, TaskType.INTENT_DETECTION, max_passes=2, options=options))
            try:
                await asyncio.wait_for(selected.wait(), 5)
                store._entries[key].lease_until = 0
                claim = await store.claim(key, "new", 60)
                await store.record_stop_intent(claim, (await store.load(key)).revision, FailedOutcome(diagnostic="stop"))
                proceed.set()
                with self.assertRaises(OwnershipConflict):
                    await task
                self.assertTrue(all(call.args[2] == 0 for call in compile_plan.call_args_list))
            finally:
                proceed.set()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_stop_reopens_before_compile_or_restore(self):
        schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)
        key = ExecutionId("stopping")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stop.sqlite"
            with closing(sqlite3.connect(path)) as db:
                db.executescript(schema.read_text("utf-8"))
                engine = runtime(Group, store=SQLiteExecutionStore(db), enable_stop_intent=True)
                with self.assertRaises(ExecutionStopping) as stopped:
                    await engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
                intent = stopped.exception.intent
                self.assertIsInstance(intent.outcome, CompletedOutcome)
                self.assertEqual(TypeAdapter(ResolveResult[Text]).validate_json(intent.outcome.result_json).data, Text(text="joined"))
            with closing(sqlite3.connect(path)) as db:
                engine = runtime(Group, store=SQLiteExecutionStore(db))
                with (patch.object(PipelineHooks, "compile", side_effect=AssertionError("compiled during stop")),
                      patch.object(CheckpointCodec, "restore", side_effect=AssertionError("restored during stop"))):
                    for operation in (engine.resume(key, max_passes=1, options=options),
                                      engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)):
                        with self.assertRaises(ExecutionStopping) as recovered:
                            await operation
                        self.assertEqual(recovered.exception.intent, intent)

    async def test_final_replay_after_reopen(self):
        from app.application.engine.contracts.invocation.inputWait import Failed
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        key = ExecutionId("terminal-replay")
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)

        class Pack:
            receipt = None

            async def read_closed(self, command):
                return self.receipt

            async def close(self, command):
                self.receipt = CloseReceipt(command.store_id, command.execution_id, command.stop_revision)
                raise ConnectionError("reply lost after CLOSED")

        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "dag.sqlite"
                payload = Path(directory) / "count=5"
                payload.write_bytes(b"held data")
                pack = Pack()

                class Lifecycle:
                    async def validate_restored(self, output: Text):
                        (Path(directory) / output.text).read_bytes()

                with closing(sqlite3.connect(path)) as db:
                    db.executescript(schema)
                    store = SQLiteExecutionStore(db)
                    engine = runtime(store=store, pack_closer=pack, entry_lifecycle=Lifecycle())
                    assert isinstance(engine, DAGEngine)
                    with patch.object(store, "finalize", side_effect=Crash):
                        if failed:
                            with patch.object(Pipeline, "start", side_effect=PythonNodeError(TestNodeError(item_id=1))):
                                with self.assertRaises(Crash):
                                    await engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
                        else:
                            with self.assertRaises(Crash):
                                await engine.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
                    pending = await store.load(key)
                    assert pending.stop_intent is not None
                    self.assertIsNone(pending.final_revision)
                    outcome = pending.stop_intent.outcome
                    if failed:
                        assert isinstance(outcome, FailedOutcome)
                        expected = Failed(outcome.diagnostic)
                    else:
                        assert isinstance(outcome, CompletedOutcome)
                        expected = TypeAdapter(ResolveResult[Text]).validate_json(outcome.result_json)
                        self.assertEqual(expected.data, Text(text="count=5"))

                with closing(sqlite3.connect(path)) as db:
                    store = SQLiteExecutionStore(db)
                    engine = runtime(store=store, pack_closer=pack)
                    assert isinstance(engine, DAGEngine)
                    # A close acknowledgement alone cannot authorize the final write.
                    with (patch.object(pack, "read_closed", return_value=None),
                          patch.object(pack, "close", return_value=pack.receipt),
                          self.assertRaises(RestoreFailure)):
                        await engine.resume(key, max_passes=1, options=options)
                    self.assertEqual(await store.load(key), pending)
                    commit = store.finalize

                    async def lost_reply(claim, revision, closed):
                        await commit(claim, revision, closed)
                        raise Crash()

                    with (patch.object(store, "finalize", side_effect=lost_reply),
                          patch.object(store, "release"), patch.object(pack, "close", side_effect=AssertionError)):
                        with self.assertRaises(Crash):
                            await engine.resume(key, max_passes=1, options=options)
                    self.assertTrue(db.execute("SELECT lease_until > unixepoch('subsec') FROM dag_executions").fetchone()[0])

                with closing(sqlite3.connect(path)) as db:
                    store = SQLiteExecutionStore(db)
                    engine = runtime(store=store, entry_lifecycle=Lifecycle())
                    assert isinstance(engine, DAGEngine)
                    for available in (True, False):
                        if not available:
                            payload.unlink()
                        with (patch.object(store, "claim", side_effect=AssertionError),
                              patch.object(PipelineHooks, "compile", side_effect=AssertionError),
                              patch.object(CheckpointCodec, "restore", side_effect=AssertionError),
                              patch.object(Lifecycle, "validate_restored", side_effect=AssertionError),
                              patch.object(Path, "open", side_effect=AssertionError)):
                            with self.assertRaises(RestoreFailure):
                                await engine.run(key, TaskType.SCENE_INIT, max_passes=1, options=options)
                            self.assertEqual(await engine.resume(key, max_passes=1, options=options), expected)
                            self.assertEqual(await engine.run(key, TaskType.INTENT_DETECTION,
                                                              max_passes=1, options=options), expected)

    async def test_final_replay_checks_owner_type_and_integrity(self):
        from tests.dag_typing.invocations.test_input_wait import Session
        from unittest.mock import AsyncMock

        key = ExecutionId("private-result")
        options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)
        schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript(schema.read_text("utf-8"))
            store = SQLiteExecutionStore(db)
            pack = AsyncMock()
            async def receipt(command):
                return CloseReceipt(command.store_id, command.execution_id, command.stop_revision)
            pack.read_closed.side_effect = receipt
            owner = runtime(store=store, pack_closer=pack, interaction=Session("a"))
            assert isinstance(owner, DAGEngine)
            await owner.run(key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
            stranger = runtime(store=store, interaction=Session("b"))
            assert isinstance(stranger, DAGEngine)
            with patch.object(store, "claim", side_effect=AssertionError):
                with self.assertRaises(PermissionError):
                    await stranger.resume(key, max_passes=1, options=options)
                with patch.object(PipelineHooks, "response_type", Count), self.assertRaises(RestoreFailure):
                    await owner.resume(key, max_passes=1, options=options)
                db.execute("UPDATE dag_executions SET checksum='corrupt' WHERE execution_id=?", (key,))
                with self.assertRaises(RestoreFailure):
                    await owner.resume(key, max_passes=1, options=options)

    async def test_prior_phase_output_is_bound_to_post_root(self):
        from app.dataModel.engine.dag.executionPhase import ExecutionPhase
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        seen = []
        class Pre(Source):
            async def execute(self, input):
                seen.append("pre")
                return input

        pre_ref = RequiredOutput(OutputRef(Pre.id, Payload))
        class Post(Left):
            async def prepare_input(self, view):
                return view.require(pre_ref)

            async def execute(self, input):
                seen.append("post")
                return input

        registry, bindings = NodeRegistry(), GraphBindings()
        for node, reads in ((Pre(), ()), (Post(phase=ExecutionPhase.POST_LLM, deps=(Pre.id,)), (pre_ref,))):
            registry.register_python(type(node), FakeExecutor, NodeContract(Payload, Payload, ContractId(node.id),
                                     ContractVersion("1"), reads, error_types=()))
            bindings.nodes[node.id] = node
        compiler = GraphCompiler(registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        class Hooks(PipelineHooks):
            response_type = Payload
            reads = (RequiredOutput(OutputRef(Post.id, Payload)),)

        store = MemoryExecutionStore()
        executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {FakeExecutor: FakeExecutor()},
                               invocation_options=InvocationOptions(store, workers=1, invocation_limit=2))
        plan = compiler.compile(GraphRuleState(), invocation_root=Post.id)
        engine = DAGEngine(executor, None, registry, Hooks(plan),
                           None, ExecutionSnapshotService(), SnapshotStore())
        result = await engine.run(ExecutionId("mixed"), TaskType.INTENT_DETECTION, max_passes=1,
                                  options=LLMExecutionOptions(player_message="", language="ru", repair_iterations=0,
                                                              repair_mode=RepairMode.MAXIMUM))
        self.assertTrue(result.ok)
        self.assertEqual(seen, ["pre", "post"])

        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        from app.dataModel.engine.dag.records import OutputRecord
        execution = ExecutionId("mixed")
        saved = await store.load(execution)
        graph = InvocationGraph.model_validate_json(saved.blob)
        prior = next(record for record in graph.records.values() if record.node_id == Pre.id)
        for contract_id, version in ((ContractId("other"), prior.version), (prior.contract_id, ContractVersion("99"))):
            foreign = OutputRecord[Payload](identity=prior.identity(), contract_id=contract_id, contract_version=version,
                                            output=Payload())
            with self.subTest(contract_id=contract_id, version=version), self.assertRaises(RestoreFailure):
                await executor.run_invocation(plan, execution, Post.id, graph.revision, store, owner="test",
                                              workers=1, invocation_limit=2, prior_outputs=(foreign,))
        self.assertEqual(saved, await store.load(execution))

    async def test_foreign_prior_read_rejected_before_checkpoint(self):
        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        from app.dataModel.engine.dag.executionPhase import ExecutionPhase
        from app.dataModel.engine.dag.identity import ExecutionIdentity, InvocationId
        from app.dataModel.engine.dag.records import DependencyRead, OutputRecord

        registry, bindings = NodeRegistry(), GraphBindings()
        for node in (Source(), Left(deps=(Source.id,), phase=ExecutionPhase.POST_LLM)):
            contract = NodeContract(Payload, Payload, ContractId(node.id), ContractVersion("1"), (), error_types=())
            registry.register_python(type(node), FakeExecutor, contract)
            bindings.nodes[node.id] = node
        compiler = GraphCompiler(registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        plan = compiler.compile(GraphRuleState(), invocation_root=Left.id)
        executor, _ = runtime()
        store = MemoryExecutionStore()
        execution, revision = ExecutionId("prior-read"), PlanRevision("1")
        args = (plan, execution, Left.id, revision, store)
        options = dict(owner="test", workers=1, invocation_limit=2)
        source = ExecutionIdentity(execution_id=execution, node_id=Source.id, invocation_id=InvocationId("root/source"),
                                   attempt=1, plan_revision=revision)
        foreign = ExecutionIdentity(execution_id=execution, node_id=NodeId("foreign"),
                                    invocation_id=InvocationId("call-9/foreign"), attempt=1, plan_revision=revision)
        read = DependencyRead(producer=foreign.node_id, contract_id=ContractId("foreign"),
                              contract_version=ContractVersion("1"), required=True, result=foreign)

        def prior(reads):
            return OutputRecord[Payload](identity=source, contract_id=ContractId(Source.id),
                                         contract_version=ContractVersion("1"), output=Payload(), reads=reads)

        with self.assertRaisesRegex(RestoreFailure, "foreign dependency read"):
            await executor.run_invocation(*args, prior_outputs=(prior((read,)),), **options)
        initial = await store.load(execution)
        self.assertEqual(initial.revision, 0)
        self.assertEqual(InvocationGraph.model_validate_json(initial.blob).records[source.invocation_id].reads, ())
        correct = await executor.run_invocation(*args, prior_outputs=(prior(()),), **options)
        self.assertEqual(correct.status, "SUCCEEDED")
        saved = await store.load(execution)
        replay = await executor.run_invocation(*args, **options)
        self.assertEqual(replay, correct)
        self.assertEqual(await store.load(execution), saved)

    async def test_slow_effect_retains_lease(self):
        await self.check_slow_effect(2)

    async def test_slow_effect_retains_one_second_lease(self):
        await self.check_slow_effect(1)

    async def check_slow_effect(self, lease_seconds):
        from unittest.mock import patch
        calls = []
        async def slow_effect(hooks, view):
            calls.append(1)
            await asyncio.sleep(2.2)
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            from contextlib import closing
            path = Path(directory) / "effects.sqlite"
            with closing(sqlite3.connect(path)) as a, closing(sqlite3.connect(path)) as b:
                a.executescript(schema)
                key = ExecutionId("lease")
                options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=RepairMode.MAXIMUM)
                with patch.object(PipelineHooks, "apply_effects", slow_effect):
                    result = await runtime(store=SQLiteExecutionStore(a), lease_seconds=lease_seconds).run(
                        key, TaskType.INTENT_DETECTION, max_passes=1, options=options)
                    self.assertEqual((await SQLiteExecutionStore(b).load(key)).status, "COMPLETED")
                    self.assertEqual(result, await runtime(store=SQLiteExecutionStore(b)).resume(key, max_passes=1, options=options))
                self.assertEqual(calls, [1])

    async def test_prior_outputs_cannot_replace_terminal_root(self):
        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        from app.dataModel.engine.dag.records import OutputRecord

        store = MemoryExecutionStore()
        executor, plan = runtime(Group)
        execution = ExecutionId("protected-root")
        args = (plan, execution, Group.id, PlanRevision("1"), store)
        options = dict(owner="test", workers=1, invocation_limit=4)
        root = await executor.run_invocation(*args, **options)
        saved = await store.load(execution)
        for contract_id, version in ((root.contract_id, root.version), (ContractId("foreign"), ContractVersion("99"))):
            forged = OutputRecord[Text](identity=root.identity(), contract_id=contract_id, contract_version=version,
                                            output=Text(text="forged"))
            with self.subTest(contract=contract_id), self.assertRaises(RestoreFailure):
                await executor.run_invocation(*args, prior_outputs=(forged,), **options)
        replay = await executor.run_invocation(*args, **options)
        self.assertEqual(Text.model_validate_json(replay.terminal).text, "joined")
        checkpoint = InvocationGraph.model_validate_json((await store.load(execution)).blob)
        self.assertEqual(replay, checkpoint.records[checkpoint.root])
        self.assertEqual(saved, await store.load(execution))

    async def test_store_preserves_caller_transaction(self):
        from contextlib import closing
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "caller.sqlite"
            with closing(sqlite3.connect(path)) as a, closing(sqlite3.connect(path)) as b:
                a.executescript(schema + "\nCREATE TABLE caller(n INTEGER);")
                store = SQLiteExecutionStore(a)
                key = ExecutionId("txn")
                await store.create(key, b"initial")
                claim = await store.claim(key, "a", 30)
                for commit in (False, True):
                    a.execute("INSERT INTO caller VALUES (7)")
                    for operation in (store.create(key, b"x"), store.claim(key, "b", 30),
                                      store.checkpoint(claim, 9, "failed", b"x"), store.renew(claim, 30), store.release(claim)):
                        with self.assertRaisesRegex(RuntimeError, "active transaction"):
                            await operation
                        self.assertTrue(a.in_transaction)
                        self.assertEqual(b.execute("SELECT * FROM caller").fetchall(), [])
                    if commit:
                        a.commit()
                    else:
                        a.rollback()
                    self.assertEqual(b.execute("SELECT * FROM caller").fetchall(), [(7,)] if commit else [])
                self.assertEqual((await store.load(key)).revision, 0)
                await store.release(claim)

    async def test_prerequisite_runtime_failure_resolves_diagnostic(self):
        from unittest.mock import patch
        from app.application.engine.contracts.invocation.resumeEvent import CallRuntimeFailure
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        refs = []
        class Capture(CountCaller):
            async def resume(self, state, event):
                result = event.get(KEY, TRANSFORM)
                assert isinstance(result, CallRuntimeFailure)
                refs.append(result.diagnostic_ref)
                return Complete(Count(value=0))
        async def fail(node, input):
            raise RuntimeError("merge failed")
        store = MemoryExecutionStore()
        executor, plan = runtime(counter=Capture, diamond=True)
        key = ExecutionId("diagnostic")
        with patch.object(Merge, "execute", fail):
            await executor.run_invocation(plan, key, CountCaller.id, PlanRevision("1"), store,
                                          owner="test", workers=1, invocation_limit=8)
        graph = InvocationGraph.model_validate_json((await store.load(key)).blob)
        self.assertEqual(len(refs), 1)
        diagnostics = graph.records[refs[0].invocation_id].diagnostics
        self.assertTrue(any(d.identity == refs[0] and "/merge" in d.message for d in diagnostics))

    async def test_replay_after_resume_effect_before_checkpoint(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effects.sqlite"
            class CountWithEffect(CountCaller):
                async def resume(self, state, event):
                    result = await super().resume(state, event)
                    from contextlib import closing
                    with closing(sqlite3.connect(path)) as conn, conn:
                        conn.execute("INSERT INTO attempts VALUES (1)")
                        conn.execute("INSERT OR IGNORE INTO effects VALUES (?)", ("count/hello",))
                    return result

            class BeforeCommit(SQLiteExecutionStore):
                async def checkpoint(self, claim, revision, status, blob):
                    graph = InvocationGraph.model_validate_json(blob)
                    if any(r.node_id == COUNT.node_id and r.status == "SUCCEEDED" for r in graph.records.values()):
                        raise Crash
                    return await super().checkpoint(claim, revision, status, blob)

            db = sqlite3.connect(path)
            try:
                db.executescript("BEGIN;\n" + schema + "\nCREATE TABLE attempts(n INTEGER);"
                                 "CREATE TABLE effects(operation_id TEXT PRIMARY KEY); COMMIT;")
                executor, plan = runtime(counter=CountWithEffect)
                args = (ExecutionId("effects"), Pipeline.id, PlanRevision("1"))
                with self.assertRaises(Crash):
                    await executor.run_invocation(plan, *args, BeforeCommit(db), owner="first", workers=1, invocation_limit=5)
            finally:
                db.close()
            db = sqlite3.connect(path)
            try:
                executor, plan = runtime(counter=CountWithEffect)
                root = await executor.run_invocation(plan, *args, SQLiteExecutionStore(db), owner="next",
                                                     workers=1, invocation_limit=5)
                self.assertEqual(root.status, "SUCCEEDED")
                self.assertEqual(db.execute("SELECT count(*) FROM attempts").fetchone(), (2,))
                self.assertEqual(db.execute("SELECT count(*) FROM effects").fetchone(), (1,))
            finally:
                db.close()

    async def test_group_uses_available_workers(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        barrier = asyncio.Event()
        entries = []
        class ParallelTransform(Transform):
            async def execute(self, input):
                entries.append(input.value)
                if len(entries) == 2:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=2)
                return await super().execute(input)

        executor, plan = runtime(Group, transform=ParallelTransform)
        result = await executor.run_invocation(plan, ExecutionId("parallel"), Group.id, PlanRevision("1"),
                                               MemoryExecutionStore(), owner="test", workers=2, invocation_limit=4)
        self.assertEqual(Text.model_validate_json(result.terminal).text, "joined")

    async def test_diamond_is_local_to_each_call(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        executor, plan = runtime(diamond=True)
        key = ExecutionId("diamond")
        result = await executor.run_invocation(plan, key, Pipeline.id, PlanRevision("1"), store,
                                               owner="test", workers=2, invocation_limit=13)
        self.assertEqual(Text.model_validate_json(result.terminal).text, "count=5")
        graph = InvocationGraph.model_validate_json((await store.load(key)).blob)
        sources = [r for r in graph.records.values() if r.node_id == Source.id]
        merges = [r for r in graph.records.values() if r.node_id == Merge.id]
        self.assertEqual(len(sources), 2)
        self.assertEqual([r.attempt_counter for r in sources], [1, 1])
        self.assertEqual(len(merges), 2)
        for merge in merges:
            self.assertEqual({read.result.invocation_id for read in merge.reads}, set(merge.dependency_bindings))
            self.assertTrue(all(graph.records[k].plan_instance_id == merge.plan_instance_id for k in merge.dependency_bindings))
        merges[0].dependency_bindings = merges[1].dependency_bindings
        from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        with self.assertRaises(RestoreFailure):
            CheckpointCodec.decode(CheckpointCodec.encode(graph), plan)

    async def test_same_key_replay_is_idempotent_and_changed_input_is_rejected(self):
        from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
        _, plan = runtime()
        coordinator = InvocationCoordinator.create(plan, ExecutionId("dispatch"), PlanRevision("1"), CountCaller.id, 8, Payload())
        record = coordinator.graph.records[coordinator.graph.root]
        step = await CountCaller().start(Payload())
        coordinator.begin(record)
        coordinator.accept(record, step)
        original = coordinator.graph.model_dump_json()
        coordinator.accept(record, step)
        self.assertEqual(coordinator.graph.model_dump_json(), original)
        conflict = Call(KEY, TRANSFORM, TransformRequest(operation="count", value="other"), Payload())
        with self.assertRaises(ValueError):
            coordinator.accept(record, conflict)
        self.assertEqual(coordinator.graph.model_dump_json(), original)

    async def test_retry_same_invocation(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        executor, plan = runtime(transform=FailOnceTransform, retry_policy=lambda error, attempt: attempt == 1)
        result = await executor.run_invocation(plan, ExecutionId("retry"), Pipeline.id, PlanRevision("1"), store,
                                               owner="test", workers=1, invocation_limit=5)
        self.assertEqual(Text.model_validate_json(result.terminal), Text(text="count=5"))
        graph = InvocationGraph.model_validate_json((await store.load(ExecutionId("retry"))).blob)
        calls = [r for r in graph.records.values() if r.node_id == TRANSFORM.node_id]
        self.assertEqual([(r.step_index, r.attempt_counter) for r in calls], [(0, 2), (0, 1)])
        self.assertNotEqual(calls[0].invocation_id, calls[1].invocation_id)

    async def test_engine_restart_and_terminal_delivery(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.sqlite"
            db = sqlite3.connect(path)
            execution = ExecutionId("engine")
            options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0,
                                          repair_mode=RepairMode.MAXIMUM)
            try:
                db.executescript("BEGIN;\n" + schema + "\nCOMMIT;")
                store = InterruptedStore(db)
                store.stop_at = 6
                with self.assertRaises(Crash):
                    await runtime(store=store).run(execution, TaskType.INTENT_DETECTION, max_passes=1, options=options)
            finally:
                db.close()
            db = sqlite3.connect(path)
            try:
                store = SQLiteExecutionStore(db)
                with self.assertRaises(OwnershipConflict):
                    await store.claim(execution, "second", 30)
                with db:
                    db.execute("UPDATE dag_executions SET lease_until=unixepoch()-1")
                engine = runtime(store=store)
                result = await engine.resume(execution, max_passes=1, options=options)
                self.assertEqual(result.data, Text(text="count=5"))
                saved = await store.load(execution)
                duplicate = await runtime(store=store).resume(execution, max_passes=1, options=options)
                self.assertEqual(result, duplicate)
                self.assertEqual(saved, await store.load(execution))
            finally:
                db.close()

    async def test_join_and_fencing(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.sqlite"
            first, second = sqlite3.connect(path), sqlite3.connect(path)
            try:
                first.executescript("BEGIN;\n" + schema + "\nCOMMIT;")
                a, b = SQLiteExecutionStore(first), SQLiteExecutionStore(second)
                key = ExecutionId("group")
                executor, plan = runtime(Group)
                result = await executor.run_invocation(plan, key, Group.id, PlanRevision("1"), a,
                                                       owner="worker", workers=1, invocation_limit=4)
                self.assertEqual(Text.model_validate_json(result.terminal).text, "joined")
                stale = await a.claim(key, "a", 60)
                with self.assertRaises(OwnershipConflict):
                    await b.claim(key, "b", 60)
                with first:
                    first.execute("UPDATE dag_executions SET lease_until=unixepoch()-1 WHERE execution_id=?", (key,))
                active = await b.claim(key, "b", 60)
                with self.assertRaises(OwnershipConflict):
                    await a.renew(stale, 60)
                saved = await b.load(key)
                with self.assertRaises(OwnershipConflict):
                    await a.checkpoint(stale, saved.revision, saved.status, saved.blob)
                await b.checkpoint(active, saved.revision, saved.status, saved.blob)
                with self.assertRaises(OwnershipConflict):
                    await b.checkpoint(active, saved.revision, saved.status, saved.blob)
            finally:
                first.close()
                second.close()

    async def test_every_checkpoint_with_one_worker(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        for stop_at in range(1, 19):
            with self.subTest(stop_at=stop_at), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "execution.sqlite"
                db = sqlite3.connect(path)
                try:
                    db.executescript("BEGIN;\n" + schema + "\nCOMMIT;")
                    store = InterruptedStore(db)
                    store.stop_at = stop_at
                    executor, plan = runtime()
                    args = (ExecutionId("flow"), Pipeline.id, PlanRevision("1"))
                    options = dict(owner="worker", workers=1, invocation_limit=10)
                    with self.assertRaises(Crash):
                        await executor.run_invocation(plan, *args, store, **options)
                    before = InvocationGraph.model_validate_json((await store.load(args[0])).blob)
                finally:
                    db.close()
                db = sqlite3.connect(path)
                try:
                    store = SQLiteExecutionStore(db)
                    with self.assertRaises(OwnershipConflict):
                        await store.claim(args[0], "next", 30)
                    with db:
                        db.execute("UPDATE dag_executions SET lease_until=unixepoch()-1")
                    executor, plan = runtime()
                    root = await executor.run_invocation(plan, *args, store, **options)
                    self.assertEqual(Text.model_validate_json(root.terminal).text, "count=5")
                    after = InvocationGraph.model_validate_json((await store.load(args[0])).blob)
                    calls = [r for r in after.records.values() if r.node_id == TRANSFORM.node_id]
                    self.assertEqual(len({r.invocation_id for r in calls}), 2)
                    for key, old in before.records.items():
                        if old.status == "RUNNING":
                            self.assertGreater(after.records[key].attempt_counter, old.attempt_counter)
                finally:
                    db.close()
