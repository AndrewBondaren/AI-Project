"""A2.3: local typed execution with no catalog/state/trace writes."""

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
import weakref

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision, NodeOutcome
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.taskType import TaskType
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.diagnostics import CancellationReason, CancellationSource
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import OutputRecord
from tests.dag_typing.fixtures import (
    AlwaysLeafOutput, FakeExecutor, GraphProducer, LeafOutput, NodeInput, REQUIRED_LEAF, RecordingValidator,
)


class GateError(NodeError):
    message: str = "test message"


class FatalError(NodeError):
    message: str = "test fatal message"


def error_policy(error: GateError | FatalError) -> GateSignal | None:
    return GateSignal(TaskType.SCENE_NARRATION, "test transition") if isinstance(error, GateError) else None


@dataclass(frozen=True, kw_only=True)
class RunnerNode(PythonNode[NodeInput, LeafOutput, GateError | FatalError]):
    id: NodeId = NodeId("runner")
    prepared: NodeInput = field(default_factory=lambda: NodeInput(value=3))
    produced: LeafOutput = field(default_factory=lambda: LeafOutput(value=4))
    events: list[str] = field(default_factory=list, compare=False)
    prepare: Callable[[DAGReadView], Awaitable[NodeInput]] | None = None
    operation: Callable[[NodeInput], Awaitable[LeafOutput]] | None = None

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        self.events.append("prepare")
        view.require(REQUIRED_LEAF)
        view.record_domain_read("test.world", DomainRevision("r1"))
        return await self.prepare(view) if self.prepare is not None else self.prepared

    async def execute(self, input: NodeInput) -> LeafOutput:
        self.events.append("execute")
        return await self.operation(input) if self.operation is not None else self.produced


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.structural = ContractValidator()
        self.semantic = NodeValidator()
        self.runner = NodeRunner(self.structural, self.semantic)
        self.executor = PythonNodeExecutor()
        self.configure()

    def configure(self, validator=None, *, errors=(GateError, FatalError), policy=error_policy):
        registry = NodeRegistry()
        producer_contract = NodeContract(NodeInput, LeafOutput, ContractId("producer"), ContractVersion("1"), (), error_types=())
        registry.register_python(GraphProducer, FakeExecutor, producer_contract)
        self.contract = NodeContract(NodeInput, LeafOutput, ContractId("runner"), ContractVersion("1"), (REQUIRED_LEAF,), validator=validator, error_types=errors, error_policy=policy if errors else None)
        registry.register_python(RunnerNode, PythonNodeExecutor, self.contract)
        self.registration = registry.get(NodeId("runner"), self.contract)
        self.catalog = DAGContext(ExecutionId("execution-1"), registry)
        self.producer = self.catalog.begin_attempt(NodeId("producer"), PlanRevision("plan-1"))
        self.catalog.publish(OutputRecord[LeafOutput](identity=self.producer, contract_id=producer_contract.contract_id,
                           contract_version=producer_contract.version, output=LeafOutput(value=1)))

    async def run_node(self, node=None, **kwargs):
        node = RunnerNode() if node is None else node
        self.identity = self.catalog.begin_attempt(NodeId("runner"), PlanRevision("plan-1"))
        self.view = self.catalog.read_view(NodeId("runner"))
        return await self.runner.run(node, self.view, self.identity, self.registration, self.executor, **kwargs)

    async def test_success_is_local_preserves_payload_and_leaves_attempt_open(self):
        node = RunnerNode(produced=AlwaysLeafOutput(value=5))
        outcome = await self.run_node(node, pass_number=2, level=3)
        self.assertEqual(node.events, ["prepare", "execute"])
        self.assertEqual(outcome.status, NodeStatus.SUCCESS)
        self.assertIs(outcome.output, node.produced)
        self.assertEqual(outcome.reads[0].result, self.producer)
        self.assertEqual(outcome.domain_reads[0].revision, DomainRevision("r1"))
        self.assertEqual(self.catalog.current_outputs, (self.producer,))
        self.assertEqual(self.catalog.closed_attempts, (self.producer,))
        self.assertNotIn("AlwaysLeafOutput", repr(outcome))
        self.assertGreaterEqual(outcome.completed_at, outcome.started_at)
        self.assertEqual((outcome.diagnostics[0].pass_number, outcome.diagnostics[0].level), (2, 3))
        self.catalog.publish(OutputRecord[LeafOutput](identity=outcome.identity, contract_id=self.contract.contract_id,
                             contract_version=self.contract.version, output=outcome.output,
                             reads=outcome.reads, domain_reads=outcome.domain_reads))

    async def test_wrong_or_forged_input_stops_before_execute(self):
        for prepared in ({"value": 3}, LeafOutput(value=3), NodeInput.model_construct(value="bad")):
            with self.subTest(prepared=prepared):
                self.configure()
                node = RunnerNode(prepared=prepared)
                outcome = await self.run_node(node)
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertIsNone(outcome.output)
                self.assertEqual(node.events, ["prepare"])
                self.assertEqual(outcome.validation.status, ValidationStatus.FAIL)

    async def test_wrong_or_forged_output_never_reaches_semantic_callback(self):
        for produced in ({"value": 3}, NodeInput(value=3), LeafOutput.model_construct(value="bad")):
            with self.subTest(produced=produced):
                callback = RecordingValidator(ValidationResult(status=ValidationStatus.OK))
                self.configure(callback)
                outcome = await self.run_node(RunnerNode(produced=produced))
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertIsNone(outcome.output)
                self.assertEqual(callback.contexts, [])

    async def test_semantic_fail_retry_user_error_preserve_original_report(self):
        for status in (ValidationStatus.FAIL, ValidationStatus.RETRY, ValidationStatus.USER_ERROR):
            with self.subTest(status=status):
                result = ValidationResult(status=status, dsl_patch=["domain instruction"])
                callback = RecordingValidator(result)
                self.configure(callback)
                outcome = await self.run_node(pass_number=4)
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertIs(outcome.validation, result)
                self.assertIsNone(outcome.output)
                self.assertEqual(callback.contexts[0].pass_number, 4)
                self.assertEqual(callback.contexts[0].identity, outcome.identity)

    async def test_prepare_exception_and_execute_exception_keep_evidence_without_error_payload(self):
        async def fail(_):
            raise RuntimeError("SECRET_OUTPUT")
        for field_name in ("prepare", "operation"):
            with self.subTest(field=field_name):
                self.configure()
                outcome = await self.run_node(RunnerNode(**{field_name: fail}))
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertEqual(len(outcome.reads), 1)
                self.assertEqual(len(outcome.domain_reads), 1)
                self.assertNotIn("SECRET_OUTPUT", repr(outcome))
                self.assertIn("RuntimeError", outcome.diagnostics[0].message)
                self.catalog.close_attempt(outcome.identity)

    async def test_missing_required_input_is_failed_with_absence_evidence(self):
        self.catalog.begin_attempt(NodeId("producer"), PlanRevision("plan-2"))
        outcome = await self.run_node()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.reads[0].result)
        self.assertTrue(outcome.reads[0].required)

    async def test_declared_pre_llm_gate_from_prepare_or_execute_has_no_output(self):
        async def gate(_):
            raise PythonNodeError(GateError(message="SECRET_OUTPUT"))
        for field_name in ("prepare", "operation"):
            with self.subTest(field=field_name):
                self.configure()
                outcome = await self.run_node(RunnerNode(**{field_name: gate}))
                self.assertEqual(outcome.status, NodeStatus.GATED)
                self.assertEqual(outcome.gate, GateSignal(TaskType.SCENE_NARRATION, "test transition"))
                self.assertIsNone(outcome.output)
                self.assertEqual(self.catalog.current_outputs, (self.producer,))
                self.assertNotIn("SECRET_OUTPUT", repr(outcome))

    async def test_undeclared_fatal_post_llm_and_invalid_policy_are_failures(self):
        for error, errors, phase, policy in (
            (GateError(), (), ExecutionPhase.PRE_LLM, error_policy),
            (FatalError(), (FatalError,), ExecutionPhase.PRE_LLM, error_policy),
            (GateError(), (GateError,), ExecutionPhase.POST_LLM, error_policy),
            (GateError(), (GateError,), ExecutionPhase.PRE_LLM, lambda error: "invalid"),
        ):
            with self.subTest(error=type(error), errors=errors, phase=phase):
                self.configure(errors=errors, policy=policy)
                async def fail(_):
                    raise PythonNodeError(error)
                outcome = await self.run_node(RunnerNode(operation=fail, phase=phase))
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertIsNone(outcome.gate)
                self.assertIs(outcome.error, error if errors else None)

    async def test_validator_exception_cannot_become_gate(self):
        def callback(ctx):
            raise PythonNodeError(GateError())
        self.configure(callback)
        outcome = await self.run_node()
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.gate)
        self.assertIsNone(outcome.error)

    async def test_concrete_error_reaches_policy_and_outcome_without_copy_or_commit(self):
        error = GateError(message="structured detail")
        seen = []
        def policy(value):
            seen.append(value)
            return GateSignal(TaskType.SCENE_INIT)
        async def fail(input):
            raise PythonNodeError(error)
        self.configure(policy=policy)
        outcome = await self.run_node(RunnerNode(operation=fail))
        self.assertIs(seen[0], error)
        self.assertIs(outcome.error, error)
        self.assertEqual(outcome.status, NodeStatus.GATED)
        self.assertFalse(hasattr(outcome, "failure_code"))
        self.assertFalse(hasattr(outcome.gate, "code"))
        self.assertIsNone(self.catalog.node_error(NodeId("runner"), self.contract))
        self.catalog.close_error(outcome.identity, outcome.error, self.contract)
        self.assertIs(self.catalog.node_error(NodeId("runner"), self.contract), error)

    async def test_bad_error_pojo_is_rejected_before_policy(self):
        def policy(error):
            self.fail("malformed error must not reach policy")
        async def fail(input):
            raise PythonNodeError(GateError.model_construct(message=1))
        self.configure(policy=policy)
        outcome = await self.run_node(RunnerNode(operation=fail))
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsNone(outcome.error)
        self.assertFalse(outcome.validation.ok)

    async def test_missing_policy_is_failed_with_original_error(self):
        error = GateError()
        async def fail(input):
            raise PythonNodeError(error)
        self.configure(policy=None)
        outcome = await self.run_node(RunnerNode(operation=fail))
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIs(outcome.error, error)

    async def test_policy_exception_is_local_failure_and_keeps_original_error(self):
        error = GateError()
        def policy(value):
            raise RuntimeError("PRIVATE_POLICY_DATA")
        async def fail(input):
            raise PythonNodeError(error)
        self.configure(policy=policy)
        outcome = await self.run_node(RunnerNode(operation=fail))
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIs(outcome.error, error)
        self.assertNotIn("PRIVATE_POLICY_DATA", repr(outcome))

    async def test_cancellation_requested_by_policy_cannot_become_gate(self):
        def policy(error):
            asyncio.current_task().cancel()
            return GateSignal(TaskType.SCENE_INIT)
        async def fail(input):
            raise PythonNodeError(GateError())
        self.configure(policy=policy)
        task = asyncio.create_task(self.run_node(RunnerNode(operation=fail)))
        outcome = await task
        self.assertEqual(outcome.status, NodeStatus.CANCELLED)
        self.assertIsNone(outcome.error)

    async def test_error_outcome_does_not_retain_input_through_exception_traceback(self):
        async def fail(input):
            raise PythonNodeError(FatalError())
        node = RunnerNode(operation=fail)
        reference = weakref.ref(node.prepared)
        outcome = await self.run_node(node)
        del node
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(outcome.status, NodeStatus.FAILED)
        self.assertIsInstance(outcome.error, FatalError)

    async def test_cancellation_waits_for_cleanup_and_keeps_evidence(self):
        entered, cleaned = asyncio.Event(), asyncio.Event()
        async def operation(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()
        task = asyncio.create_task(self.run_node(RunnerNode(operation=operation)))
        await entered.wait()
        task.cancel()
        outcome = await task
        self.assertTrue(cleaned.is_set())
        self.assertEqual(outcome.status, NodeStatus.CANCELLED)
        self.assertIsNone(outcome.output)
        self.assertEqual(len(outcome.reads), 1)
        event = outcome.diagnostics[0]
        self.assertEqual((event.cancel_source, event.cancel_reason), (CancellationSource.UNKNOWN, CancellationReason.UNKNOWN))
        self.assertLessEqual(event.cancel_observed_at, outcome.completed_at)
        self.assertIsNone(event.cancel_requested_at)
        self.assertEqual(self.catalog.current_outputs, (self.producer,))
        self.catalog.close_attempt(outcome.identity)

    async def test_node_raised_cancellation_during_prepare_or_execute_is_not_success(self):
        async def cancel(_):
            raise asyncio.CancelledError
        for field_name in ("prepare", "operation"):
            with self.subTest(field=field_name):
                self.configure()
                outcome = await self.run_node(RunnerNode(**{field_name: cancel}))
                self.assertEqual(outcome.status, NodeStatus.CANCELLED)
                self.assertIsNone(outcome.output)

    async def test_suppressed_cancellation_cannot_publish_success(self):
        entered = asyncio.Event()
        async def operation(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return LeafOutput(value=7)
        task = asyncio.create_task(self.run_node(RunnerNode(operation=operation)))
        await entered.wait()
        task.cancel()
        self.assertEqual((await task).status, NodeStatus.CANCELLED)

    async def test_wrong_binding_executor_identity_or_view_fails_before_node_work(self):
        node = RunnerNode()
        identity = self.catalog.begin_attempt(node.id, PlanRevision("plan-1"))
        view = self.catalog.read_view(node.id)
        foreign_view = replace(view, _execution_id=ExecutionId("foreign"))
        for arguments in (
            (identity.model_copy(update={"node_id": NodeId("other")}), self.registration, self.executor, view),
            (identity, self.registration, FakeExecutor(), view),
            (identity, self.registration, self.executor, foreign_view),
            (identity, self.registration, self.executor, replace(view, consumer=NodeId("other"))),
        ):
            with self.subTest(arguments=arguments):
                current_identity, registration, executor, current_view = arguments
                outcome = await self.runner.run(node, current_view, current_identity, registration, executor)
                self.assertEqual(outcome.status, NodeStatus.FAILED)
                self.assertEqual(node.events, [])

    async def test_executor_only_delegates_and_preserves_input_output_identity(self):
        prepared = NodeInput(value=8)
        output = LeafOutput(value=9)
        async def operation(input):
            self.assertIs(input, prepared)
            return output
        node = RunnerNode(operation=operation)
        self.assertIs(await self.executor.execute(node, prepared), output)
        self.assertEqual(node.events, ["execute"])


class OutcomeTests(unittest.TestCase):
    def test_structural_outcome_invariants_and_frozen_metadata(self):
        from tests.dag_typing.fixtures import identity
        common = dict(identity=identity(), started_at=1.0, completed_at=2.0)
        for invalid in (
            dict(status=NodeStatus.RUNNING), dict(status=NodeStatus.SUCCESS),
            dict(status=NodeStatus.FAILED, output=LeafOutput(value=1)),
            dict(status=NodeStatus.GATED),
            dict(status=NodeStatus.SUCCESS, output=LeafOutput(value=1), gate=GateSignal(TaskType.SCENE_NARRATION)),
            dict(status=NodeStatus.SUCCESS, output=LeafOutput(value=1), validation=ValidationResult(status=ValidationStatus.FAIL)),
            dict(status=NodeStatus.SUCCESS, output=LeafOutput(value=1), error=GateError()),
            dict(status=NodeStatus.CANCELLED, error=GateError()),
            dict(status=NodeStatus.GATED, gate=GateSignal(TaskType.SCENE_INIT)),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                NodeOutcome(**common, **invalid)
        outcome = NodeOutcome(**common, status=NodeStatus.FAILED)
        with self.assertRaises(FrozenInstanceError):
            outcome.status = NodeStatus.SUCCESS
        self.assertEqual({item.value for item in LevelDecision}, {"continue", "cancel", "fail", "replan"})

    def test_import_does_not_load_legacy_production_nodes(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run([sys.executable, "-c", "import sys,json; from app.application.engine.runtime.execution.nodeRunner import NodeRunner; print(json.dumps([n for n in sys.modules if n == 'app.application.engine.nodes' or n.startswith('app.application.engine.nodes.')]))"], cwd=root,
                                env=dict(os.environ, PYTHONPATH=str(root / "backend")), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
