"""A3.2: independent memory owners and metadata-only trace retention."""

import asyncio
from dataclasses import replace
import gc
from typing import Never
import unittest
import weakref

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import PlanRevision
from tests.dag_typing.execution import test_level as levels
from tests.dag_typing.fixtures import TestNodeError


class RetentionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = levels.LevelTests()
        self.case.setUp()
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        await asyncio.sleep(0)  # release completed gather/shield callbacks
        self.service = ExecutionSnapshotService[Never]()

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def output_ref(self, snapshot):
        return weakref.ref(snapshot.catalog.record(levels.LevelRoot.id, self.case.contracts[levels.LevelRoot.id]).output)

    async def test_release_frees_output_even_when_trace_and_levels_are_kept(self):
        snapshot = self.service.capture(self.case.state)
        ref = self.output_ref(snapshot)
        traces, levels_metadata = self.case.state.traces, self.case.state.levels
        del snapshot
        self.case.state.release()
        gc.collect()
        self.assertIsNone(ref())
        self.assertTrue(traces)
        self.assertTrue(levels_metadata)
        self.assertTrue(self.case.state.is_released)
        with self.assertRaisesRegex(RuntimeError, "released"):
            self.service.capture(self.case.state)
        with self.assertRaisesRegex(RuntimeError, "released"):
            self.case.state.begin_phase(PlanRevision("next"))

    async def test_snapshot_and_store_own_payload_after_execution_release(self):
        snapshot = self.service.capture(self.case.state)
        ref = self.output_ref(snapshot)
        store = SnapshotStore[Never]()
        store.save(snapshot)
        key = snapshot.metadata.execution_id
        self.case.state.release()
        del snapshot
        gc.collect()
        self.assertIsNotNone(ref())
        store.delete(key)
        gc.collect()
        self.assertIsNone(ref())

    async def test_deleting_store_does_not_release_active_state_ownership(self):
        snapshot = self.service.capture(self.case.state)
        ref = self.output_ref(snapshot)
        store = SnapshotStore[Never]()
        store.save(snapshot)
        store.delete(snapshot.metadata.execution_id)
        del snapshot
        gc.collect()
        self.assertIsNotNone(ref())
        self.case.state.release()
        gc.collect()
        self.assertIsNone(ref())

    async def test_replacement_releases_old_payload_and_retains_new(self):
        store = SnapshotStore[Never]()
        snapshot = self.service.capture(self.case.state)
        old = self.output_ref(snapshot)
        store.save(snapshot)
        del snapshot
        await self.case.execute(pass_number=1, rerun=(levels.LevelRoot.id,))
        snapshot = self.service.capture(self.case.state)
        new = self.output_ref(snapshot)
        store.save(snapshot)
        del snapshot
        gc.collect()
        self.assertIsNone(old())
        self.assertIsNotNone(new())

    async def test_restored_state_is_an_independent_owner_of_same_payload(self):
        snapshot = self.service.capture(self.case.state)
        ref = self.output_ref(snapshot)
        restored = await self.service.restore(snapshot, self.case.registry)
        self.case.state.release()
        del snapshot
        gc.collect()
        self.assertIsNotNone(ref())
        restored.release()
        gc.collect()
        self.assertIsNone(ref())

    async def test_terminal_release_frees_request_local_lifecycle_binding(self):
        class Lifecycle:
            async def validate_restored(self, output):
                pass
        lifecycle = Lifecycle()
        ref = weakref.ref(lifecycle)
        registry = NodeRegistry()
        registry.register_python(levels.LevelRoot, PythonNodeExecutor,
                                 replace(self.case.contracts[levels.LevelRoot.id], lifecycle=lifecycle))
        snapshot = self.service.capture(self.case.state)
        restored = await self.service.restore(snapshot, registry)
        del registry, lifecycle
        gc.collect()
        self.assertIsNotNone(ref())
        restored.release()
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(len(snapshot.catalog.output_identities), 1)

    async def test_error_payload_is_not_retained_by_trace_after_release(self):
        async def fail(input):
            raise PythonNodeError(TestNodeError(item_id=8))
        case = levels.LevelTests()
        case.setUp()
        case.node(levels.LevelRoot, job=fail)
        case.setup_plan()
        await case.execute()
        await asyncio.sleep(0)  # task results own errors until callbacks drain
        snapshot = self.service.capture(case.state)
        ref = weakref.ref(snapshot.catalog.node_error(levels.LevelRoot.id, case.contracts[levels.LevelRoot.id]))
        traces = case.state.traces
        del snapshot
        case.state.release()
        gc.collect()
        self.assertIsNone(ref())
        self.assertTrue(traces)

    async def test_active_and_open_writers_cannot_release_payloads(self):
        state = self.case.state
        state.begin_phase(PlanRevision("next"))
        with self.assertRaisesRegex(RuntimeError, "active"):
            state.release()
        state.end_phase()
        identity = state.catalog.begin_attempt(levels.LevelRoot.id, PlanRevision("next"))
        with self.assertRaisesRegex(RuntimeError, "open attempts"):
            state.release()
        self.assertFalse(state.is_released)
        state.catalog.close_attempt(identity)
        state.release()
        state.release()  # idempotent terminal release
