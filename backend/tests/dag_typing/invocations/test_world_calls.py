import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never

from pydantic import BaseModel, ConfigDict, RootModel

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
from app.application.engine.contracts.invocation.executionStore import OwnershipConflict
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
from app.dataModel.engine.dag.invocations.record import InvocationGraph
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from tests.dag_typing.fixtures import TestNodeError, FakeExecutor, GraphBindings, GraphRuleState


class Payload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NamedTarget(Payload):
    world_uid: str
    location_uid: str


PORT = NamedTarget(world_uid="fixture-world", location_uid="port")


class BaseReceipt(Payload):
    publication: str
    source: Literal["found_light", "published_full"] = "published_full"
    scope: NamedTarget = PORT
    artifact_ref: str = "full/world-17"
    completion_receipt: str = "published/17"


class Selection(Payload):
    location: NamedTarget
    interaction_id: str
    session_uid: str
    accepted_base: BaseReceipt


class Detailed(Payload):
    detailed_ref: str


class EntryState(Payload):
    waiting_for: Literal["selection", "load"]


class LoadRequest(Payload):
    selection: Selection
    player_uid: str
    operation_id: str


class Loaded(Payload):
    start_location: NamedTarget
    detailed: Detailed
    resolved_position: tuple[int, int, int]
    completion_receipt: str


class WorldRequest(Payload):
    stage: Literal["light/full", "detailed"]
    location: str
    accepted_base: BaseReceipt | None = None


class WorldResult(RootModel[BaseReceipt | Detailed]):
    model_config = ConfigDict(frozen=True)


def target(name, input_type, output_type):
    return CallTarget(NodeId(name), ContractId(name), ContractVersion("1"), input_type, output_type,
                      (TestNodeError,) if name == "world_creation" else ())


WORLD = target("world_creation", WorldRequest, WorldResult)
SELECT = target("select_start_location", Payload, Selection)
LOAD = target("load_player_into_world", LoadRequest, Loaded)
KEY = CallKey("world")


@dataclass(frozen=True, kw_only=True)
class World(PythonNode[WorldRequest, WorldResult, TestNodeError]):
    id: NodeId = WORLD.node_id

    async def prepare_input(self, view):
        raise AssertionError("called target requires explicit input")

    async def execute(self, input):
        if input.location == "failed":
            raise PythonNodeError(TestNodeError(item_id=1))
        if input.location == "cancelled":
            raise asyncio.CancelledError
        if input.stage == "light/full":
            return WorldResult(BaseReceipt(publication="full-17"))
        assert input.accepted_base == BaseReceipt(publication="full-17")
        return WorldResult(Detailed(detailed_ref=input.location + "/detail-18"))


class Workflow(ResumablePythonNode):
    async def prepare_input(self, view):
        return Payload()


@dataclass(frozen=True, kw_only=True)
class Select(Workflow):
    id: NodeId = SELECT.node_id

    async def start(self, input):
        return Call(KEY, WORLD, WorldRequest(stage="light/full", location="port"), input)

    async def resume(self, state, event):
        result = event.get(KEY, WORLD)
        assert isinstance(result, CallSuccess) and isinstance(result.output.root, BaseReceipt)
        return Complete(Selection(location=PORT, accepted_base=result.output.root,
                                  interaction_id="selection-1", session_uid="session-1"))


@dataclass(frozen=True, kw_only=True)
class Load(Workflow):
    id: NodeId = LOAD.node_id

    async def start(self, input):
        return Call(KEY, WORLD, WorldRequest(stage="detailed", location=input.selection.location.location_uid,
                                             accepted_base=input.selection.accepted_base), input)

    async def resume(self, state, event):
        result = event.get(KEY, WORLD)
        assert isinstance(result, CallSuccess) and isinstance(result.output.root, Detailed)
        return Complete(Loaded(start_location=state.selection.location, detailed=result.output.root,
                               resolved_position=(12, 7, 0), completion_receipt=state.operation_id))


@dataclass(frozen=True, kw_only=True)
class Entry(Workflow):
    id: NodeId = NodeId("initialize_world_entry")

    async def start(self, input):
        return Call(CallKey("select"), SELECT, input, EntryState(waiting_for="selection"))

    async def resume(self, state, event):
        if state.waiting_for == "selection":
            result = event.get(CallKey("select"), SELECT)
            assert isinstance(result, CallSuccess)
            return Call(CallKey("load"), LOAD, LoadRequest(selection=result.output, player_uid="player-1",
                                                          operation_id="load-17"), EntryState(waiting_for="load"))
        result = event.get(CallKey("load"), LOAD)
        assert isinstance(result, CallSuccess)
        return Complete(result.output)


@dataclass(frozen=True, kw_only=True)
class Group(Entry):
    async def start(self, input):
        return CallGroup(tuple(CallRequest(CallKey(name), WORLD, WorldRequest(stage="light/full", location=name))
                               for name in ("failed", "cancelled", "ok")), Payload())

    async def resume(self, state, event):
        assert isinstance(event.get(CallKey("failed"), WORLD), CallFailure)
        assert isinstance(event.get(CallKey("cancelled"), WORLD), CallCancelled)
        assert isinstance(event.get(CallKey("ok"), WORLD), CallSuccess)
        return Complete(Detailed(detailed_ref="joined"))


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


def runtime(entry=Entry, store=None, world=World, retry_policy=None, diamond=False, select=Select):
    registry, bindings = NodeRegistry(), GraphBindings()
    if diamond:
        for cls, deps in ((Source, ()), (Left, (Source.id,)), (Right, (Source.id,)), (Merge, (Left.id, Right.id))):
            reads = tuple(RequiredOutput(OutputRef(n, Payload)) for n in deps) if cls is Merge else ()
            contract = NodeContract(Payload, Payload, ContractId(cls.id), ContractVersion("1"), reads, error_types=())
            registry.register_python(cls, FakeExecutor, contract)
            bindings.nodes[cls.id] = cls(deps=deps)
    for cls, declaration, calls in (
        (entry, target(entry.id, Payload, Detailed if entry is Group else Loaded), (WORLD,) if entry is Group else (SELECT, LOAD)),
        (select, SELECT, (WORLD,)), (Load, LOAD, (WORLD,)), (world, WORLD, ()),
    ):
        state_type = {Load: LoadRequest, Entry: EntryState}.get(cls, Payload)
        continuation = ContinuationContract(ContractId(f"{cls.id}.state"), ContractVersion("1"), state_type) if calls else None
        contract = NodeContract(declaration.input_type, declaration.output_type, declaration.contract_id,
                                declaration.version, (), calls=calls, continuation=continuation, error_types=declaration.error_types,
                                retry_policy=retry_policy if cls is world else None)
        register = registry.register_resumable if calls else registry.register_python
        register(cls, FakeExecutor, contract)
        bindings.nodes[cls.id] = cls(deps=(Merge.id,)) if diamond and cls is world else cls()
    compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
    compiler.precompile()
    config = InvocationOptions(store, workers=1, invocation_limit=16) if store else None
    executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {FakeExecutor: FakeExecutor()},
                           invocation_options=config)
    plan = compiler.compile(GraphRuleState(), invocation_root=entry.id)
    if store is not None:
        return DAGEngine(executor, None, registry, EntryHooks(plan), None, ExecutionSnapshotService(), SnapshotStore())
    return executor, plan


class EntryHooks:
    consumer = NodeId("result")
    reads = (RequiredOutput(OutputRef(Entry.id, Loaded)),)
    response_type = Loaded

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
                declared = replace(WORLD, version=ContractVersion("2")) if kind == "version" else WORLD
                calls = (replace(declared, node_id=NodeId("unknown")),) if kind == "unknown" else (declared,)
                continuation = ContinuationContract(ContractId("select.state"), ContractVersion("1"), Payload)
                registry.register_resumable(Select, FakeExecutor, NodeContract(Payload, Selection, SELECT.contract_id,
                    SELECT.version, (), error_types=(), calls=calls, continuation=continuation))
                registry.register_python(World, FakeExecutor, NodeContract(WorldRequest, WorldResult, WORLD.contract_id,
                    WORLD.version, (), error_types=WORLD.error_types))
                bindings.nodes[Select.id] = Select()
                bindings.nodes[World.id] = World(deps=(Select.id,) if kind == "mixed-cycle" else (),
                    phase=ExecutionPhase.POST_LLM if kind == "cross-phase" else ExecutionPhase.PRE_LLM)
                compiler = GraphCompiler(registry, bindings, compile_rules=lambda _: (), evaluate_rules=lambda *_: True)
                with self.assertRaises((ValueError, TypeError)):
                    compiler.precompile()

    def test_bad_group_and_incompatible_restore(self):
        from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
        from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
        from app.application.engine.contracts.invocation.executionStore import RestoreFailure
        request = WORLD.request(KEY, WorldRequest(stage="light/full", location="port"))
        for requests in ((), (request, request)):
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                CallGroup(requests, Payload())
        _, plan = runtime()
        coordinator = InvocationCoordinator.create(plan, ExecutionId("restore"), PlanRevision("1"), Entry.id, 5, None)
        coordinator.graph.records[coordinator.graph.root].version = ContractVersion("unknown")
        with self.assertRaises(RestoreFailure):
            CheckpointCodec.decode(CheckpointCodec.encode(coordinator.graph), plan)


class FailOnceWorld(World):
    async def execute(self, input):
        if input.stage == "light/full" and not getattr(self, "attempted", False):
            object.__setattr__(self, "attempted", True)
            raise PythonNodeError(TestNodeError(item_id=1))
        return await super().execute(input)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_replay_after_resume_effect_before_checkpoint(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effects.sqlite"
            class SelectWithEffect(Select):
                async def resume(self, state, event):
                    result = await super().resume(state, event)
                    from contextlib import closing
                    with closing(sqlite3.connect(path)) as conn, conn:
                        conn.execute("INSERT INTO attempts VALUES (1)")
                        conn.execute("INSERT OR IGNORE INTO effects VALUES (?)", ("selection/full-17",))
                    return result

            class BeforeCommit(SQLiteExecutionStore):
                async def checkpoint(self, claim, revision, status, blob):
                    graph = InvocationGraph.model_validate_json(blob)
                    if any(r.node_id == SELECT.node_id and r.status == "SUCCEEDED" for r in graph.records.values()):
                        raise Crash
                    return await super().checkpoint(claim, revision, status, blob)

            db = sqlite3.connect(path)
            try:
                db.executescript("BEGIN;\n" + schema + "\nCREATE TABLE attempts(n INTEGER);"
                                 "CREATE TABLE effects(operation_id TEXT PRIMARY KEY); COMMIT;")
                executor, plan = runtime(select=SelectWithEffect)
                args = (ExecutionId("effects"), Entry.id, PlanRevision("1"))
                with self.assertRaises(Crash):
                    await executor.run_invocation(plan, *args, BeforeCommit(db), owner="first", workers=1, invocation_limit=5)
            finally:
                db.close()
            db = sqlite3.connect(path)
            try:
                executor, plan = runtime(select=SelectWithEffect)
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
        class ParallelWorld(World):
            async def execute(self, input):
                entries.append(input.location)
                if len(entries) == 2:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=2)
                return await super().execute(input)

        executor, plan = runtime(Group, world=ParallelWorld)
        result = await executor.run_invocation(plan, ExecutionId("parallel"), Group.id, PlanRevision("1"),
                                               MemoryExecutionStore(), owner="test", workers=2, invocation_limit=4)
        self.assertEqual(Detailed.model_validate_json(result.terminal).detailed_ref, "joined")

    async def test_diamond_is_local_to_each_call(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        executor, plan = runtime(diamond=True)
        key = ExecutionId("diamond")
        result = await executor.run_invocation(plan, key, Entry.id, PlanRevision("1"), store,
                                               owner="test", workers=2, invocation_limit=13)
        self.assertEqual(Loaded.model_validate_json(result.terminal).detailed.detailed_ref, "port/detail-18")
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
        coordinator = InvocationCoordinator.create(plan, ExecutionId("dispatch"), PlanRevision("1"), Select.id, 8, Payload())
        record = coordinator.graph.records[coordinator.graph.root]
        step = await Select().start(Payload())
        coordinator.begin(record)
        coordinator.accept(record, step)
        original = coordinator.graph.model_dump_json()
        coordinator.accept(record, step)
        self.assertEqual(coordinator.graph.model_dump_json(), original)
        conflict = Call(KEY, WORLD, WorldRequest(stage="light/full", location="other"), Payload())
        with self.assertRaises(ValueError):
            coordinator.accept(record, conflict)
        self.assertEqual(coordinator.graph.model_dump_json(), original)

    async def test_retry_same_invocation(self):
        from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
        store = MemoryExecutionStore()
        executor, plan = runtime(world=FailOnceWorld, retry_policy=lambda error, attempt: attempt == 1)
        result = await executor.run_invocation(plan, ExecutionId("retry"), Entry.id, PlanRevision("1"), store,
                                               owner="test", workers=1, invocation_limit=5)
        self.assertEqual(Loaded.model_validate_json(result.terminal).detailed, Detailed(detailed_ref="port/detail-18"))
        graph = InvocationGraph.model_validate_json((await store.load(ExecutionId("retry"))).blob)
        calls = [r for r in graph.records.values() if r.node_id == WORLD.node_id]
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
                self.assertEqual(result.data, Loaded(start_location=PORT, detailed=Detailed(detailed_ref="port/detail-18"),
                                                     resolved_position=(12, 7, 0), completion_receipt="load-17"))
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
                self.assertEqual(Detailed.model_validate_json(result.terminal).detailed_ref, "joined")
                stale = await a.claim(key, "a", 60)
                with self.assertRaises(OwnershipConflict):
                    await b.claim(key, "b", 60)
                with first:
                    first.execute("UPDATE dag_executions SET lease_until=unixepoch()-1 WHERE execution_id=?", (key,))
                active = await b.claim(key, "b", 60)
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
                    args = (ExecutionId("flow"), Entry.id, PlanRevision("1"))
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
                    self.assertEqual(Loaded.model_validate_json(root.terminal).detailed.detailed_ref, "port/detail-18")
                    after = InvocationGraph.model_validate_json((await store.load(args[0])).blob)
                    calls = [r for r in after.records.values() if r.node_id == WORLD.node_id]
                    self.assertEqual(len({r.invocation_id for r in calls}), 2)
                    for key, old in before.records.items():
                        if old.status == "RUNNING":
                            self.assertGreater(after.records[key].attempt_counter, old.attempt_counter)
                finally:
                    db.close()
