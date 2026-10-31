"""A3.2: restore admission, lifecycle order and continuation without execution."""

import asyncio
from dataclasses import replace
from typing import Never
import unittest
from unittest.mock import patch

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, PlanRevision
from tests.dag_typing.execution import test_level as levels
from tests.dag_typing.fixtures import LeafOutput, CompositeOutput, TestNodeError, TestOtherError


class Lifecycle:
    def __init__(self, calls, failure=None):
        self.calls = calls
        self.failure = failure

    async def validate_restored(self, value):
        self.calls.append(("output", value))
        if self.failure is not None:
            raise self.failure


class Extension:
    snapshot_type = LeafOutput
    contract_id = ContractId("test.restore.extension")
    version = ContractVersion("1")

    def __init__(self, calls, failure=None):
        self.calls = calls
        self.failure = failure
        self.value = LeafOutput(value=42)

    def capture(self):
        return self.value

    async def validate_restored(self, value):
        self.calls.append(("validate extension", value))
        if self.failure is not None:
            raise self.failure

    async def restore(self, value):
        self.calls.append(("restore extension", value))


class RestoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = levels.LevelTests()
        self.case.setUp()
        self.case.node(levels.LevelRoot)
        self.case.node(levels.LevelTail, deps=("root",), reads=(levels.required("root"),))
        self.case.setup_plan()
        await self.case.execute(pass_number=2)
        self.service = ExecutionSnapshotService[Never]()
        self.snapshot = self.service.capture(self.case.state)

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def registry(self, changes=None, omit=(), extra=False):
        registry = NodeRegistry()
        for reg in self.case.registry.graph_registrations():
            if reg.node_id not in omit:
                registry.register_python(reg.node_cls, PythonNodeExecutor,
                                         replace(reg.contract, **(changes or {}).get(reg.node_id, {})))
        if extra:
            registry.register_python(levels.LevelLeft, PythonNodeExecutor,
                                     replace(self.case.contracts[levels.LevelRoot.id], contract_id=ContractId("extra")))
        return registry

    async def test_round_trip_preserves_identity_payload_provenance_and_control(self):
        registry = self.registry()
        calls = tuple(tuple(node.calls) for node in self.case.bindings.nodes.values())
        state = await self.service.restore(self.snapshot, registry)
        self.assertIsNot(state, self.case.state)
        self.assertEqual(self.service.capture(state), self.snapshot)
        self.assertFalse(state.is_active)
        for registration in registry.graph_registrations():
            actual = state.catalog.capture().record(registration.node_id, registration.contract)
            saved = self.snapshot.catalog.record(registration.node_id, registration.contract)
            self.assertIs(actual, saved)
        self.assertEqual(calls, tuple(tuple(node.calls) for node in self.case.bindings.nodes.values()))
        state.begin_phase(PlanRevision("plan-2"), 3)
        identity = state.catalog.begin_attempt(levels.LevelRoot.id, PlanRevision("plan-2"))
        self.assertEqual(identity.attempt, 2)
        self.assertEqual(identity.execution_id, self.snapshot.metadata.execution_id)
        self.assertEqual(state.catalog.current_outputs, ())  # transitive invalidation restored
        self.assertEqual(len(self.snapshot.catalog.output_identities), 2)
        with self.assertRaisesRegex(RuntimeError, "already closed"):
            state.catalog.close_attempt(self.snapshot.catalog.output_identities[0])

    async def test_unchanged_restored_outputs_are_reused_without_node_calls(self):
        self.case.state = await self.service.restore(self.snapshot, self.case.registry)
        before = tuple(tuple(node.calls) for node in self.case.bindings.nodes.values())
        await self.case.execute(pass_number=3)
        self.assertEqual(before, tuple(tuple(node.calls) for node in self.case.bindings.nodes.values()))
        self.assertEqual(self.case.state.catalog.attempt_counters, self.snapshot.metadata.attempt_counters)

    async def test_format_mismatch_precedes_callbacks(self):
        calls = []
        bad = replace(self.snapshot, metadata=self.snapshot.metadata.model_copy(update={"format_version": 999}))
        with self.assertRaisesRegex(ValueError, "format version"):
            await self.service.restore(bad, self.registry({levels.LevelRoot.id: {"lifecycle": Lifecycle(calls)}}))
        self.assertEqual(calls, [])

    async def test_contract_id_version_and_node_set_mismatch(self):
        for changes in ({"version": ContractVersion("2")}, {"contract_id": ContractId("other")}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "root.*id/version"):
                await self.service.restore(self.snapshot, self.registry({levels.LevelRoot.id: changes}))
        with self.assertRaisesRegex(ValueError, "root.*not registered"):
            await self.service.restore(self.snapshot, self.registry(omit=(levels.LevelRoot.id,)))
        with self.assertRaisesRegex(ValueError, "node set"):
            await self.service.restore(self.snapshot, self.registry(extra=True))

    async def test_class_and_changed_read_declarations_are_checked_before_callbacks(self):
        calls = []
        for changes, error in (({"output_type": CompositeOutput}, TypeError), ({"reads": ()}, PermissionError)):
            with self.subTest(changes=changes), self.assertRaises(error):
                await self.service.restore(self.snapshot, self.registry({
                    levels.LevelRoot.id: {"lifecycle": Lifecycle(calls)}, levels.LevelTail.id: changes,
                }))
        self.assertEqual(calls, [])

    async def test_value_only_restore_does_not_serialize_copy_or_revalidate_output_schema(self):
        with patch.object(LeafOutput, "model_validate", side_effect=AssertionError("schema rerun")), \
             patch.object(LeafOutput, "model_dump", side_effect=AssertionError("dump")), \
             patch.object(LeafOutput, "__deepcopy__", side_effect=AssertionError("copy")):
            state = await self.service.restore(self.snapshot, self.registry())
        self.assertEqual(state.catalog.current_outputs, self.snapshot.catalog.output_identities)

    async def test_all_output_and_extension_validation_precede_extension_restore(self):
        calls = []
        extension = Extension(calls)
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        registry = self.registry({node: {"lifecycle": Lifecycle(calls)} for node in self.case.registry.ids()})
        await service.restore(snapshot, registry)
        self.assertEqual([name for name, _ in calls], ["output", "output", "validate extension", "restore extension"])
        self.assertIs(calls[-1][1], snapshot.extension)

    async def test_invalid_domain_ref_reports_producer_attempt_ref_and_preserves_snapshot(self):
        calls = []
        extension = Extension(calls)
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        store = SnapshotStore[LeafOutput]()
        store.save(snapshot)
        registry = self.registry({levels.LevelTail.id: {"lifecycle": Lifecycle(calls, LookupError("ref=pack:missing reason=deleted"))}})
        with self.assertRaisesRegex(ValueError, "tail.*attempt 1.*pack:missing.*deleted"):
            await service.restore(snapshot, registry)
        self.assertEqual([name for name, _ in calls], ["output"])
        self.assertEqual(len(snapshot.catalog.output_identities), 2)
        self.assertIs(store.load(snapshot.metadata.execution_id), snapshot)
        self.assertEqual(self.service.capture(self.case.state), self.snapshot)

    async def test_extension_binding_and_class_mismatch(self):
        calls = []
        extension = Extension(calls)
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        with self.assertRaisesRegex(ValueError, "extension contract"):
            await self.service.restore(snapshot, self.registry())
        with self.assertRaisesRegex(ValueError, "extension contract"):
            await service.restore(self.snapshot, self.registry())
        extension.version = ContractVersion("2")
        with self.assertRaisesRegex(ValueError, "extension contract"):
            await service.restore(snapshot, self.registry())
        extension.version = ContractVersion("1")
        extension.snapshot_type = CompositeOutput
        with self.assertRaisesRegex(TypeError, "extension class"):
            await service.restore(snapshot, self.registry())
        self.assertEqual(calls, [])

    async def test_extension_validation_failure_never_restores(self):
        calls = []
        extension = Extension(calls, LookupError("ref=session:missing"))
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        with self.assertRaisesRegex(ValueError, "extension.*session:missing"):
            await service.restore(snapshot, self.registry())
        self.assertEqual([name for name, _ in calls], ["validate extension"])

    async def test_extension_restore_failure_preserves_stored_snapshot(self):
        calls = []
        extension = Extension(calls)
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        store = SnapshotStore[LeafOutput]()
        store.save(snapshot)
        async def fail(value):
            raise RuntimeError("session unavailable")
        extension.restore = fail
        with self.assertRaisesRegex(ValueError, "session unavailable"):
            await service.restore(snapshot, self.registry())
        self.assertIs(store.load(snapshot.metadata.execution_id), snapshot)

    async def test_idle_registered_nodes_are_restored_and_checked(self):
        state = ExecutionState(self.snapshot.metadata.execution_id, self.case.registry,
                               plan_revision=PlanRevision("idle"))
        snapshot = self.service.capture(state)
        restored = await self.service.restore(snapshot, self.registry())
        self.assertEqual(self.service.capture(restored), snapshot)
        with self.assertRaisesRegex(ValueError, "root.*id/version"):
            await self.service.restore(snapshot, self.registry({levels.LevelRoot.id: {"version": ContractVersion("2")}}))

    async def test_current_context_is_distinct_from_reused_output_context(self):
        await self.case.executor.run_python_phase(
            self.case.plan, self.case.state, levels.ExecutionPhase.PRE_LLM, PlanRevision("plan-2"), pass_number=3,
        )
        snapshot = self.service.capture(self.case.state)
        restored = await self.service.restore(snapshot, self.registry())
        self.assertEqual(restored.plan_revision, PlanRevision("plan-2"))
        self.assertEqual(restored.pass_number, 3)
        self.assertEqual(restored.catalog.current_outputs[0].plan_revision, PlanRevision("plan-1"))
        self.assertEqual(restored.attempt_passes, snapshot.attempt_passes)

    async def test_cancellation_propagates_without_extension_restore(self):
        calls = []
        extension = Extension(calls)
        service = ExecutionSnapshotService(extension)
        snapshot = service.capture(self.case.state)
        registry = self.registry({levels.LevelRoot.id: {"lifecycle": Lifecycle(calls, asyncio.CancelledError())}})
        with self.assertRaises(asyncio.CancelledError):
            await service.restore(snapshot, registry)
        self.assertEqual([name for name, _ in calls], ["output"])

    async def test_error_and_gate_round_trip_and_error_class_admission(self):
        async def job(input):
            raise PythonNodeError(TestNodeError(item_id=7))
        case = levels.LevelTests()
        case.setUp()
        case.node(levels.LevelRoot, job=job, policy=levels.gate_policy)
        case.setup_plan()
        await case.execute()
        snapshot = self.service.capture(case.state)
        restored = await self.service.restore(snapshot, case.registry)
        self.assertEqual(self.service.capture(restored), snapshot)
        self.assertIs(restored.catalog.node_error(levels.LevelRoot.id, case.contracts[levels.LevelRoot.id]),
                      snapshot.catalog.node_error(levels.LevelRoot.id, case.contracts[levels.LevelRoot.id]))
        registry = NodeRegistry()
        registry.register_python(levels.LevelRoot, PythonNodeExecutor,
                                 replace(case.contracts[levels.LevelRoot.id], error_types=(TestOtherError,)))
        with self.assertRaisesRegex(TypeError, "error class"):
            await self.service.restore(snapshot, registry)

    async def test_cancelled_status_and_closed_attempts_round_trip(self):
        async def cancel(input):
            raise asyncio.CancelledError
        case = levels.LevelTests()
        case.setUp()
        case.node(levels.LevelRoot, job=cancel)
        case.setup_plan()
        await case.execute()
        snapshot = self.service.capture(case.state)
        self.assertEqual(self.service.capture(await self.service.restore(snapshot, case.registry)), snapshot)
