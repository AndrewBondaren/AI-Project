"""Test-only registered CALL transport; the stage spy does not write an artifact."""

import asyncio
import unittest
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.application.engine.contracts.invocation.callTarget import CallTarget
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.executionBindings import ResolveResult
from app.application.engine.contracts.outputRef import OutputRef, RequiredOutput
from app.application.engine.contracts.invocation.continuationContract import ContinuationContract
from app.application.engine.contracts.invocation.nodeStep import Call, Complete
from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallFailure, CallRuntimeFailure, CallSuccess
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dagEngine import DAGEngine
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.taskType import TaskType
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.contracts.invocation.executionStore import OwnershipConflict, RestoreFailure
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInput, PreparedArtifact
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInput
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractVersion, ExecutionId, NodeId, PlanRevision
from tests.dag_typing.fixtures import FakeExecutor, GraphBindings, GraphRuleState, TestNodeError
from tests.snapshotCore.support.fakeSection import FakePrepared


class PreparedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    value: PreparedArtifact[FakePrepared]


class StageOutput(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    count: int


class State(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    phase: str


PREPARE = CallTarget(NodeId("test.identity.prepare"), ContractId("test.identity.prepare"), ContractVersion("1"),
                     ArtifactPrepareStageInput[FakePrepared], PreparedOutput, ())
STAGE = CallTarget(NodeId("test.identity.stage"), ContractId("test.identity.stage"), ContractVersion("1"),
                   ArtifactStageInput[FakePrepared], StageOutput, (TestNodeError,))


@dataclass(frozen=True, kw_only=True)
class Prepare(PythonNode):
    id: NodeId = PREPARE.node_id
    seen: list[object] = None
    descriptor: object = None

    async def prepare_input(self, view):
        raise AssertionError("CALL must supply input")

    async def execute(self, input):
        self.seen.append(input.content)
        return PreparedOutput(value=PreparedArtifact[FakePrepared](content=input.content, descriptor=self.descriptor))


@dataclass(frozen=True, kw_only=True)
class Stage(PythonNode):
    id: NodeId = STAGE.node_id
    seen: list[object] = None
    behavior: str = "success"
    entered: asyncio.Event | None = None
    block: asyncio.Event | None = None

    async def prepare_input(self, view):
        raise AssertionError("CALL must supply input")

    async def execute(self, input):
        self.seen.append(input.prepared)
        if self.entered is not None:
            self.entered.set()
        if self.block is not None:
            await self.block.wait()
        if self.behavior == "error":
            raise PythonNodeError(TestNodeError(item_id=1))
        if self.behavior == "retry" and len(self.seen) == 1:
            raise PythonNodeError(TestNodeError(item_id=2))
        if self.behavior == "cancel":
            raise asyncio.CancelledError
        if self.behavior == "runtime":
            raise RuntimeError("test runtime fault")
        return StageOutput(count=len(input.prepared.content.values))


@dataclass(frozen=True, kw_only=True)
class Route(ResumablePythonNode):
    id: NodeId = NodeId("test.identity.route")
    lease: OperationLeaseRef = None
    seen: list[object] = None
    source: ArtifactPrepareStageInput[FakePrepared] | None = None

    async def prepare_input(self, view):
        if self.source is None:
            raise AssertionError("root input required")
        return self.source

    async def start(self, input):
        self.seen.append(input.content)
        return Call(CallKey("prepare"), PREPARE, input, State(phase="prepare"))

    async def resume(self, state, event):
        if state.phase == "prepare":
            result = event.get(CallKey("prepare"), PREPARE)
            assert isinstance(result, CallSuccess)
            self.seen.append(result.output.value)
            return Call(CallKey("stage"), STAGE,
                        ArtifactStageInput[FakePrepared](lease=self.lease, prepared=result.output.value),
                        State(phase="stage"))
        result = event.get(CallKey("stage"), STAGE)
        if isinstance(result, (CallFailure, CallCancelled, CallRuntimeFailure)):
            self.seen.append(result)
            return Complete(StageOutput(count={CallFailure: -1, CallCancelled: -2,
                                               CallRuntimeFailure: -3}[type(result)]))
        assert isinstance(result, CallSuccess)
        return Complete(result.output)


class LiveIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_registered_prepare_stage_transport(self):
        # Explicit test-only descriptor; no production format binding or writer.
        from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind
        from app.dataModel.registryKey import RegistryKey
        from app.dataModel.artifacts.references import ArtifactFormatRegistry
        content = FakePrepared(values=(1, 2))
        descriptor = ArtifactRef(kind=ArtifactKind.SQL_ROWS, format_key=RegistryKey[ArtifactFormatRegistry]("test.rows"),
                                 format_version=1, content_hash="0" * 64, nbytes=2, row_count=2)
        lease = OperationLeaseRef(operation_id="test", world_uid="world", kind=OperationKind.PACK_ACTIVATION,
                                  preparation_fingerprint="0" * 64, fence=1)
        seen_prepare, seen_stage, seen_route = [], [], []
        registry, bindings = NodeRegistry(), GraphBindings()
        for cls, target, calls, continuation in (
            (Prepare, PREPARE, (), None), (Stage, STAGE, (), None),
            (Route, CallTarget(Route.id, ContractId(Route.id), ContractVersion("1"),
                               ArtifactPrepareStageInput[FakePrepared], StageOutput, ()),
             (PREPARE, STAGE), ContinuationContract(ContractId("test.identity.state"), ContractVersion("1"), State)),
        ):
            registry.register_resumable(cls, FakeExecutor, NodeContract(target.input_type, target.output_type,
                target.contract_id, target.version, (), calls=calls, continuation=continuation, error_types=target.error_types)) if calls else \
                registry.register_python(cls, FakeExecutor, NodeContract(target.input_type, target.output_type,
                    target.contract_id, target.version, (), error_types=target.error_types,
                    retry_policy=(lambda error, attempts: error.item_id == 2 and attempts < 2)
                    if cls is Stage else None))
        bindings.nodes[PREPARE.node_id] = Prepare(seen=seen_prepare, descriptor=descriptor)
        bindings.nodes[STAGE.node_id] = Stage(seen=seen_stage)
        bindings.nodes[Route.id] = Route(lease=lease, seen=seen_route)
        compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
        compiler.precompile()
        plan = compiler.compile(GraphRuleState(), invocation_root=Route.id)
        executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {FakeExecutor: FakeExecutor()})
        store = MemoryExecutionStore()
        request = ArtifactPrepareStageInput[FakePrepared](content=content)
        result = await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-live-identity"), Route.id,
            PlanRevision("1"), store, owner="test", workers=1, invocation_limit=8, input=request,
            identity_required=True), timeout=10)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(StageOutput.model_validate_json(result.terminal_payload()).count, 2)
        self.assertIs(seen_route[0], content)
        self.assertIs(seen_prepare[0], content)
        self.assertIs(seen_stage[0], seen_route[1])
        self.assertIs(seen_stage[0].content, content)
        self.assertEqual(len(seen_prepare), 1)
        self.assertEqual(len(seen_stage), 1)
        terminal = await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-live-identity"), Route.id,
            PlanRevision("1"), store, owner="test", workers=1, invocation_limit=8,
            identity_required=True), timeout=10)
        self.assertEqual(terminal.status, "SUCCEEDED")
        self.assertEqual((len(seen_prepare), len(seen_stage)), (1, 1))
        with self.assertRaisesRegex(RestoreFailure, "identity policy differs"):
            await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-live-identity"), Route.id,
                PlanRevision("1"), store, owner="test", workers=1, invocation_limit=8), timeout=10)
        incomplete = InvocationCoordinator.create(plan, ExecutionId("test-incomplete-identity"),
            PlanRevision("1"), Route.id, 8, request, True)
        await store.create(ExecutionId("test-incomplete-identity"), CheckpointCodec.encode(incomplete.graph))
        with self.assertRaisesRegex(RestoreFailure, "cannot resume"):
            await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-incomplete-identity"), Route.id,
                PlanRevision("1"), store, owner="test", workers=1, invocation_limit=8,
                identity_required=True), timeout=10)
        self.assertEqual((len(seen_prepare), len(seen_stage)), (1, 1))
        handoff = []
        await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-live-handoff"), Route.id,
            PlanRevision("1"), store, owner="first", workers=1, invocation_limit=8, input=request,
            identity_required=True, _coordinator_out=handoff), timeout=10)
        live_coordinator, claim = handoff[0]
        with self.assertRaises(OwnershipConflict):
            await store.claim(ExecutionId("test-live-handoff"), "second", 10)
        root = live_coordinator.graph.records[live_coordinator.graph.root]
        live_output = live_coordinator.payload(root, "terminal", root.terminal_payload(), StageOutput)
        self.assertEqual(live_output.count, 2)
        live_coordinator.clear_live()
        await store.release(claim)
        with self.assertRaises(RestoreFailure):
            live_coordinator.payload(root, "terminal", root.terminal_payload(), StageOutput)
        malformed = request.model_copy(update={"content": b"wrong"})
        with self.assertRaises((ValueError, TypeError)):
            await asyncio.wait_for(executor.run_invocation(plan, ExecutionId("test-malformed-identity"), Route.id,
                PlanRevision("1"), MemoryExecutionStore(), owner="test", workers=1, invocation_limit=8,
                input=malformed, identity_required=True), timeout=10)
        self.assertEqual((len(seen_prepare), len(seen_stage)), (2, 2))
        for behavior, expected, result_type in (("error", -1, CallFailure),
                                                ("cancel", -2, CallCancelled),
                                                ("runtime", -3, CallRuntimeFailure)):
            bindings.nodes[STAGE.node_id] = Stage(seen=seen_stage, behavior=behavior)
            variant = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
            variant.precompile()
            variant_plan = variant.compile(GraphRuleState(), invocation_root=Route.id)
            before = (len(seen_prepare), len(seen_stage))
            record = await asyncio.wait_for(executor.run_invocation(variant_plan, ExecutionId(f"test-{behavior}-identity"),
                Route.id, PlanRevision("1"), MemoryExecutionStore(), owner="test", workers=1,
                invocation_limit=8, input=request, identity_required=True), timeout=10)
            self.assertEqual(StageOutput.model_validate_json(record.terminal_payload()).count, expected)
            self.assertIsInstance(seen_route[-1], result_type)
            self.assertEqual((len(seen_prepare), len(seen_stage)), (before[0] + 1, before[1] + 1))
        retry_seen = []
        bindings.nodes[STAGE.node_id] = Stage(seen=retry_seen, behavior="retry")
        variant = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
        variant.precompile()
        retry_plan = variant.compile(GraphRuleState(), invocation_root=Route.id)
        retried = await asyncio.wait_for(executor.run_invocation(retry_plan, ExecutionId("test-retry-identity"),
            Route.id, PlanRevision("1"), MemoryExecutionStore(), owner="test", workers=1,
            invocation_limit=8, input=request, identity_required=True), timeout=10)
        self.assertEqual(StageOutput.model_validate_json(retried.terminal_payload()).count, 2)
        self.assertEqual(len(retry_seen), 2)
        self.assertIs(retry_seen[0], retry_seen[1])
        self.assertIs(retry_seen[1].content, content)
        bindings.nodes[STAGE.node_id] = Stage(seen=seen_stage)
        bindings.nodes[Route.id] = Route(lease=lease, seen=seen_route, source=request)
        public_compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
        public_compiler.precompile()
        public_plan = public_compiler.compile(GraphRuleState(), invocation_root=Route.id)

        class Hooks:
            consumer = NodeId("test.identity.result")
            reads = (RequiredOutput(OutputRef(Route.id, StageOutput)),)
            response_type = StageOutput

            def compile(self, task_type, pass_number):
                return PlanRevision("1"), public_plan

            def transition(self, view):
                return None

            async def apply_effects(self, view):
                pass

            def resolve(self, view):
                return ResolveResult(True, view.require(self.reads[0]))

        public_store = MemoryExecutionStore()
        public_executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()),
            {FakeExecutor: FakeExecutor()}, invocation_options=InvocationOptions(public_store, 1, 8,
                                                                                identity_required=True))
        engine = DAGEngine(public_executor, None, registry, Hooks(), None,
                           ExecutionSnapshotService(), SnapshotStore())
        run_options = LLMExecutionOptions(player_message="", language="ru", repair_iterations=0,
                                          repair_mode=RepairMode.MAXIMUM)
        before = (len(seen_prepare), len(seen_stage))
        public_result = await asyncio.wait_for(engine.run(ExecutionId("test-public-identity"),
            TaskType.INTENT_DETECTION, max_passes=1, options=run_options), timeout=10)
        self.assertTrue(public_result.ok)
        self.assertEqual(public_result.data.count, 2)
        self.assertEqual((len(seen_prepare), len(seen_stage)), (before[0] + 1, before[1] + 1))
        self.assertIs(seen_stage[-1], seen_route[-1])
        self.assertIs(seen_stage[-1].content, content)
        public_terminal = await asyncio.wait_for(engine.resume(ExecutionId("test-public-identity"),
            max_passes=1, options=run_options), timeout=10)
        self.assertTrue(public_terminal.ok)
        self.assertEqual(public_terminal.data.count, 2)
        self.assertEqual((len(seen_prepare), len(seen_stage)), (before[0] + 1, before[1] + 1))
        mismatched_executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()),
            {FakeExecutor: FakeExecutor()}, invocation_options=InvocationOptions(public_store, 1, 8))
        mismatched = DAGEngine(mismatched_executor, None, registry, Hooks(), None,
                               ExecutionSnapshotService(), SnapshotStore())
        with self.assertRaisesRegex(RestoreFailure, "identity policy differs"):
            await asyncio.wait_for(mismatched.resume(ExecutionId("test-public-identity"),
                max_passes=1, options=run_options), timeout=10)
        reopened = InvocationCoordinator.create(public_plan, ExecutionId("test-public-incomplete"),
            PlanRevision("1"), Route.id, 8, None, True)
        await public_store.create(ExecutionId("test-public-incomplete"), CheckpointCodec.encode(reopened.graph))
        with self.assertRaises(RestoreFailure):
            await asyncio.wait_for(engine.run(ExecutionId("test-public-incomplete"),
                TaskType.INTENT_DETECTION, max_passes=1, options=run_options), timeout=10)
        with self.assertRaises(RestoreFailure):
            await asyncio.wait_for(engine.resume(ExecutionId("test-public-incomplete"),
                max_passes=1, options=run_options), timeout=10)
        self.assertEqual((len(seen_prepare), len(seen_stage)), (before[0] + 1, before[1] + 1))

        class ReplanHooks(Hooks):
            def transition(self, view):
                return TaskType.INTENT_DETECTION

        replanning = DAGEngine(public_executor, None, registry, ReplanHooks(), None,
                               ExecutionSnapshotService(), SnapshotStore())
        before_replan = (len(seen_prepare), len(seen_stage))
        with self.assertRaisesRegex(RestoreFailure, "cannot replan"):
            await asyncio.wait_for(replanning.run(ExecutionId("test-public-replan"),
                TaskType.INTENT_DETECTION, max_passes=2, options=run_options), timeout=10)
        self.assertEqual((len(seen_prepare), len(seen_stage)),
                         (before_replan[0] + 1, before_replan[1] + 1))

        for mode in ("cancel", "owner_loss"):
            entered, blocked, active_stage = asyncio.Event(), asyncio.Event(), []
            active_route = []
            bindings.nodes[STAGE.node_id] = Stage(seen=active_stage, entered=entered, block=blocked)
            bindings.nodes[Route.id] = Route(lease=lease, seen=active_route, source=request)
            active_compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda *_: True)
            active_compiler.precompile()
            active_plan = active_compiler.compile(GraphRuleState(), invocation_root=Route.id)
            effects = []

            class ActiveHooks(Hooks):
                def compile(self, task_type, pass_number):
                    return PlanRevision("1"), active_plan

                async def apply_effects(self, view):
                    effects.append(1)

            class FailingRenewStore(MemoryExecutionStore):
                fail_renew = False

                async def renew(self, claim, seconds):
                    if self.fail_renew:
                        raise OwnershipConflict("lost test owner")
                    return await super().renew(claim, seconds)

            active_store = FailingRenewStore()
            active_executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()),
                {FakeExecutor: FakeExecutor()}, invocation_options=InvocationOptions(active_store, 1, 8,
                    lease_seconds=1, identity_required=True))
            active_engine = DAGEngine(active_executor, None, registry, ActiveHooks(), None,
                                      ExecutionSnapshotService(), SnapshotStore())
            execution = ExecutionId(f"test-public-{mode}")
            task = asyncio.create_task(active_engine.run(execution, TaskType.INTENT_DETECTION,
                                                         max_passes=1, options=run_options))
            await asyncio.wait_for(entered.wait(), timeout=10)
            if mode == "cancel":
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=10)
            else:
                active_store.fail_renew = True
                with self.assertRaises(OwnershipConflict):
                    await asyncio.wait_for(task, timeout=10)
            self.assertTrue(task.done())
            self.assertEqual(len(active_stage), 1)
            self.assertEqual(len(active_route), 2, mode)
            self.assertEqual(effects, [])
            claim = await active_store.claim(execution, "after", 10)
            await active_store.release(claim)
            with self.assertRaises(RestoreFailure):
                await asyncio.wait_for(active_engine.resume(execution, max_passes=1,
                                                             options=run_options), timeout=10)
