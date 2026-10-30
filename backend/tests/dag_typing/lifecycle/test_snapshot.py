"""A3.1: typed memory capture, ownership and immutable payload references."""

import asyncio
from dataclasses import FrozenInstanceError, replace
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Never
import unittest
from unittest.mock import patch
import weakref

from pydantic import ValidationError

from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.snapshotMetadata import SnapshotMetadata
from tests.dag_typing.execution import test_level as levels
from tests.dag_typing.fixtures import (
    AlwaysLeafOutput, CompositeOutput, ERROR_CONTRACT, LeafOutput, MutableBoundaryOutput,
    NodeInput, TestNodeError, TestOtherError, TypedErrorNode,
)


class Extension:
    snapshot_type = LeafOutput
    contract_id = ContractId("test.extension")
    version = ContractVersion("1")

    def __init__(self, value=None):
        self.value = AlwaysLeafOutput(value=42) if value is None else value
        self.calls = 0

    def capture(self):
        self.calls += 1
        return self.value

    async def restore(self, value):
        raise AssertionError("A3.1 capture must not restore")

    async def validate_restored(self, value):
        raise AssertionError("A3.1 capture must not validate domain references")


class SnapshotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.case = levels.LevelTests()
        self.case.setUp()
        self.service = ExecutionSnapshotService[Never]()

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    async def test_complete_capture_preserves_records_provenance_and_state_metadata(self):
        outputs = []
        async def job(input):
            output = AlwaysLeafOutput(value=input.value)
            outputs.append(output)
            return output
        async def prepare(view):
            view.record_domain_read("test.world", DomainRevision("r1"))
            return NodeInput(value=1)
        self.case.node(levels.LevelRoot, job=job, prepare=prepare)
        self.case.node(levels.LevelTail, deps=("root",), reads=(levels.required("root"),), job=job)
        self.case.setup_plan()
        await self.case.execute(pass_number=2)
        state = self.case.state
        snapshot = self.service.capture(state)
        self.assertEqual(snapshot.metadata.format_version, SnapshotMetadata.CURRENT_FORMAT_VERSION)
        self.assertEqual(snapshot.metadata.execution_id, state.catalog.execution_id)
        self.assertEqual(snapshot.metadata.plan_revision, PlanRevision("plan-1"))
        self.assertEqual(snapshot.metadata.pass_number, 2)
        self.assertEqual(snapshot.metadata.attempt_counters, state.catalog.attempt_counters)
        self.assertEqual(snapshot.catalog.closed_attempts, state.catalog.closed_attempts)
        self.assertEqual(snapshot.statuses, tuple(sorted(state.statuses.items())))
        self.assertEqual(snapshot.attempt_passes, ((levels.LevelRoot.id, 2), (levels.LevelTail.id, 2)))
        self.assertEqual(snapshot.traces, state.traces)
        self.assertIs(snapshot.traces[0], state.traces[0])
        self.assertIs(snapshot.levels[0], state.levels[0])
        root = snapshot.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id])
        tail = snapshot.catalog.record(levels.LevelTail.id, self.case.contracts[levels.LevelTail.id])
        self.assertIs(root.output, outputs[0])
        self.assertIs(tail.output, outputs[1])
        self.assertEqual(tail.reads[0].result, root.identity)
        self.assertEqual(root.domain_reads[0].revision, DomainRevision("r1"))
        self.assertIsNone(snapshot.extension)

    async def test_snapshot_retains_old_output_after_live_execution_advances(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        first = self.service.capture(self.case.state)
        first_record = first.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id])
        await self.case.execute(pass_number=1, rerun=(levels.LevelRoot.id,))
        second = self.service.capture(self.case.state)
        self.assertEqual(first_record.identity.attempt, 1)
        self.assertEqual(first.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id]).identity.attempt, 1)
        self.assertEqual(second.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id]).identity.attempt, 2)
        self.assertEqual(first.metadata.attempt_counters, ((levels.LevelRoot.id, 1),))
        self.assertEqual(second.metadata.attempt_counters, ((levels.LevelRoot.id, 2),))

    async def test_current_plan_revision_is_distinct_from_reused_result_revision(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        await self.case.executor.run_python_phase(self.case.plan, self.case.state, levels.ExecutionPhase.PRE_LLM, PlanRevision("plan-2"), pass_number=3)
        snapshot = self.service.capture(self.case.state)
        self.assertEqual(snapshot.metadata.plan_revision, PlanRevision("plan-2"))
        self.assertEqual(snapshot.metadata.pass_number, 3)
        self.assertEqual(snapshot.catalog.output_identities[0].plan_revision, PlanRevision("plan-1"))

    async def test_gate_error_and_selected_control_are_captured_without_error_in_trace(self):
        error = TestNodeError(item_id=7)
        async def gate(input):
            raise PythonNodeError(error)
        self.case.node(levels.LevelRoot, job=gate, policy=levels.gate_policy)
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        self.assertEqual(snapshot.decision, LevelDecision.REPLAN)
        self.assertIs(snapshot.gate, self.case.state.gate)
        self.assertIs(snapshot.catalog.node_error(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id]), error)
        self.assertEqual(snapshot.catalog.error_identities[0], snapshot.traces[0].identity)
        self.assertFalse(hasattr(snapshot.traces[0], "error"))
        self.assertNotIn("item_id", repr(snapshot))

    async def test_cancelled_execution_keeps_success_and_closed_cancelled_attempt(self):
        async def cancel(input):
            raise asyncio.CancelledError
        self.case.node(levels.LevelLeft, job=cancel)
        self.case.node(levels.LevelRight)
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        self.assertEqual(snapshot.decision, LevelDecision.CANCEL)
        self.assertEqual(len(snapshot.catalog.closed_attempts), 2)
        self.assertEqual(snapshot.catalog.output_identities[0].node_id, levels.LevelRight.id)
        self.assertEqual(dict(snapshot.statuses)[levels.LevelLeft.id], NodeStatus.CANCELLED)

    async def test_active_capture_is_rejected_before_extension_callback(self):
        entered, release = self.case.event(), self.case.event()
        async def job(input):
            entered.set()
            await release.wait()
            return LeafOutput(value=1)
        self.case.node(levels.LevelRoot, job=job)
        self.case.setup_plan()
        extension = Extension()
        service = ExecutionSnapshotService(extension)
        task = asyncio.create_task(self.case.execute())
        await self.case.reached(entered)
        with self.assertRaisesRegex(RuntimeError, "active"):
            service.capture(self.case.state)
        self.assertEqual(extension.calls, 0)
        release.set()
        await task
        self.assertFalse(self.case.state.is_active)

    async def test_open_attempt_and_unknown_context_are_rejected_without_guessing(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        with self.assertRaisesRegex(RuntimeError, "plan context"):
            self.service.capture(self.case.state)
        state = ExecutionState(ExecutionId("explicit"), self.case.registry, plan_revision=PlanRevision("known"))
        extension = Extension()
        identity = state.catalog.begin_attempt(levels.LevelRoot.id, PlanRevision("known"))
        with self.assertRaisesRegex(RuntimeError, "open attempts"):
            ExecutionSnapshotService(extension).capture(state)
        self.assertEqual(extension.calls, 0)
        state.catalog.close_attempt(identity)
        snapshot = self.service.capture(state)
        self.assertEqual(snapshot.metadata.plan_revision, PlanRevision("known"))

    async def test_ready_extension_uses_declared_schema_and_preserves_instance(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        extension = Extension()
        snapshot = ExecutionSnapshotService(extension).capture(self.case.state)
        self.assertIs(snapshot.extension, extension.value)
        self.assertEqual(snapshot.extension_contract, (extension.contract_id, extension.version))
        self.assertIn((extension.contract_id, extension.version), snapshot.metadata.contract_versions)
        self.assertEqual(extension.calls, 1)

    async def test_raw_wrong_mutable_or_forged_extension_is_rejected_without_state_change(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        before = self.case.state.catalog.capture()
        for value in ({"value": 1}, CompositeOutput(leaves=()), LeafOutput.model_construct(value="bad"), MutableBoundaryOutput(value=1)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ExecutionSnapshotService(Extension(value)).capture(self.case.state)
            self.assertEqual(self.case.state.catalog.capture(), before)

    async def test_capture_uses_no_payload_dump_copy_or_schema_revalidation(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        with patch.object(LeafOutput, "model_dump", side_effect=AssertionError("payload dump")), \
             patch.object(LeafOutput, "model_validate", side_effect=AssertionError("payload schema")), \
             patch.object(LeafOutput, "__deepcopy__", side_effect=AssertionError("payload copy")):
            snapshot = self.service.capture(self.case.state)
            self.assertIsNotNone(snapshot.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id]))

    async def test_binding_lookup_rejects_unknown_node_version_and_wrong_pojo(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        contract = self.case.contracts[levels.LevelRoot.id]
        for wrong in (replace(contract, version=ContractVersion("2")), replace(contract, output_type=CompositeOutput)):
            with self.assertRaises(TypeError):
                snapshot.catalog.record(levels.LevelRoot.id, wrong)
        with self.assertRaises(KeyError):
            snapshot.catalog.record(NodeId("missing"), contract)
        # Memory snapshot compares saved metadata and class, not a live callback identity.
        self.assertIsNotNone(snapshot.catalog.record(levels.LevelRoot.id, replace(contract)))

    async def test_error_lookup_rejects_changed_error_contract(self):
        error = TestOtherError(description="detail")
        async def fail(input):
            raise PythonNodeError(error)
        self.case.node(levels.LevelRoot, job=fail)
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        contract = self.case.contracts[levels.LevelRoot.id]
        self.assertIs(snapshot.catalog.node_error(levels.LevelRoot.id, contract), error)
        with self.assertRaises(TypeError):
            snapshot.catalog.node_error(levels.LevelRoot.id, replace(contract, error_types=(TestNodeError,)))

    async def test_versions_include_all_registry_bindings_and_reject_ambiguous_id(self):
        self.case.node(levels.LevelRoot)
        self.case.node(levels.LevelTail, deps=("root",))
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        self.assertEqual(len(snapshot.metadata.contract_versions), 2)
        extension = Extension()
        extension.contract_id = self.case.contracts[levels.LevelRoot.id].contract_id
        extension.version = ContractVersion("different")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            ExecutionSnapshotService(extension).capture(self.case.state)

    async def test_snapshot_is_frozen_and_validates_envelope_consistency(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        snapshot = self.service.capture(self.case.state)
        with self.assertRaises(FrozenInstanceError):
            snapshot.decision = LevelDecision.FAIL
        with self.assertRaises(ValueError):
            replace(snapshot, statuses=((levels.LevelRoot.id, NodeStatus.RUNNING),))
        with self.assertRaises(ValueError):
            replace(snapshot, metadata=snapshot.metadata.model_copy(update={"execution_id": ExecutionId("wrong")}))
        with self.assertRaises(ValueError):
            replace(snapshot, extension=LeafOutput(value=1))


class StoreTests(unittest.TestCase):
    def fresh(self, execution="execution-1"):
        return ExecutionSnapshotService[Never]().capture(
            ExecutionState(ExecutionId(execution), NodeRegistry(), plan_revision=PlanRevision("plan-1")),
        )

    def test_store_preserves_snapshot_instance_and_isolates_executions(self):
        first, other = self.fresh(), self.fresh("execution-2")
        store = SnapshotStore[Never]()
        store.save(first)
        store.save(other)
        self.assertIs(store.load(first.metadata.execution_id), first)
        self.assertIs(store.load(other.metadata.execution_id), other)
        replacement = self.fresh()
        store.save(replacement)
        self.assertIs(store.load(first.metadata.execution_id), replacement)
        store.delete(first.metadata.execution_id)
        self.assertIsNone(store.load(first.metadata.execution_id))
        self.assertIs(store.load(other.metadata.execution_id), other)
        store.delete(first.metadata.execution_id)

    def test_invalid_save_does_not_replace_previous_snapshot(self):
        snapshot = self.fresh()
        store = SnapshotStore[Never]()
        store.save(snapshot)
        for invalid in ({}, object()):
            with self.assertRaises(TypeError):
                store.save(invalid)
        self.assertIs(store.load(snapshot.metadata.execution_id), snapshot)

    def test_catalog_contract_id_versions_are_deduplicated_or_rejected(self):
        for version in (ContractVersion("1"), ContractVersion("2")):
            registry = NodeRegistry()
            first = NodeContract(NodeInput, LeafOutput, ContractId("shared"), ContractVersion("1"), (), error_types=())
            second = replace(first, version=version)
            registry.register_python(levels.LevelRoot, PythonNodeExecutor, first)
            registry.register_python(levels.LevelTail, PythonNodeExecutor, second)
            state = ExecutionState(ExecutionId("execution-1"), registry, plan_revision=PlanRevision("plan-1"))
            if version == ContractVersion("1"):
                snapshot = ExecutionSnapshotService[Never]().capture(state)
                self.assertEqual(snapshot.metadata.contract_versions, ((ContractId("shared"), version),))
                self.assertEqual(len(snapshot.catalog.contracts), 2)
            else:
                with self.assertRaisesRegex(ValueError, "conflicting"):
                    ExecutionSnapshotService[Never]().capture(state)
            self.assertEqual(state.catalog.attempt_counters, ())

    def test_delete_releases_store_ownership_but_not_caller_ownership(self):
        snapshot = self.fresh()
        reference = weakref.ref(snapshot)
        store = SnapshotStore[Never]()
        store.save(snapshot)
        store.delete(snapshot.metadata.execution_id)
        gc.collect()
        self.assertIs(reference(), snapshot)
        store.save(snapshot)
        key = snapshot.metadata.execution_id
        del snapshot
        store.delete(key)
        gc.collect()
        self.assertIsNone(reference())

    def test_snapshot_does_not_retain_live_contract_callback(self):
        class Callback:
            def __call__(self, ctx):
                return ValidationResult(status=ValidationStatus.OK)
        def capture():
            callback = Callback()
            reference = weakref.ref(callback)
            contract = replace(ERROR_CONTRACT, validator=callback)
            registry = NodeRegistry()
            registry.register_python(TypedErrorNode, PythonNodeExecutor, contract)
            state = ExecutionState(ExecutionId("execution-1"), registry, plan_revision=PlanRevision("plan-1"))
            return ExecutionSnapshotService[Never]().capture(state), reference
        snapshot, reference = capture()
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(snapshot.catalog.contracts), 1)

    def test_no_legacy_imports_or_new_global_store(self):
        from app.application.cancellation.typed import snapshotStore
        self.assertFalse(hasattr(snapshotStore, "snapshot_store"))
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run([sys.executable, "-c", "import sys,json; from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService; print(json.dumps([n for n in sys.modules if n in ('app.application.engine.nodes','app.application.cancellation.sessionSnapshot','app.application.cancellation.snapshotStore')]))"],
                                cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "backend")), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
