"""Execution-scoped retention probe using a real next_pass and fixture Pack bindings."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import ExecutionResponseStatus, InvocationGraph, InvocationStatus
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from tests.dag_typing.invocations.test_world_calls import runtime
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database
from tests.spatial_pack.test_pin_binding_replay import acquire, activate


class PinPassCompletionTests(IsolatedAsyncioTestCase):
    async def test_pin_survives_next_pass_until_execution_response_is_saved(self):
        execution = ExecutionId("scenario")
        _, plan = runtime()
        coord = InvocationCoordinator.create(plan, execution, PlanRevision("1"), plan.invocation_root, 16, None)
        graph = coord.graph
        invocation = graph.root
        # The single logical read in this test belongs to this execution/invocation pair.
        owner = json.dumps([execution, invocation])
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "passes.sqlite")
            async with live_database(path) as first:
                f = SqliteBlobFixture(first)
                async with first[0].transaction():
                    await first[0].conn.execute("""CREATE TABLE probe_pins(
                        pin TEXT PRIMARY KEY, owner TEXT NOT NULL, publication_id TEXT, closed INTEGER NOT NULL)""")
                async with first[1].transaction("init") as scope:
                    await first[2].initialize(scope, "w1")
                anchor = await f.open("tokens")
                await f.stager.stage(anchor, b"logical-read")
                await activate(first, f, "A", 1)
                with closing(sqlite3.connect(path)) as conn:
                    store = SQLiteExecutionStore(conn)
                    await store.create(execution, graph.model_dump_json().encode())
                    claim = await store.claim(execution, "worker", 60)
                    record = graph.records[invocation]
                    record.continuation = json.dumps({"pin_id": "logical-read"})
                    await store.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())
                    first_read = await acquire(first, f, "logical-read", owner)
                    self.assertEqual(first_read[0], "A")
                    async with f.catalog.guard(first_read[1]):
                        initial_bytes = await f.backend.read_verified(first_read[1], max_bytes=first_read[1].nbytes)
                    self.assertEqual(decode_manifest(initial_bytes).world_map_cells, 1)
                    record.attempt_counter = 1
                    record.status = InvocationStatus.SUCCEEDED
                    record.terminal = "{}"
                    self.assertEqual(graph.checkpoint_status(), InvocationStatus.SUCCEEDED)
                    revision = await store.checkpoint(claim, 1, graph.checkpoint_status(), graph.model_dump_json().encode())
                    coord.next_pass(plan.invocation_root, PlanRevision("2"), set(), record.plan_instance_id)
                    self.assertEqual((graph.root, record.status, record.continuation, record.terminal),
                                     (invocation, InvocationStatus.READY, None, None))
                    await store.checkpoint(claim, revision, graph.checkpoint_status(), graph.model_dump_json().encode())
                    await store.release(claim)

            async with live_database(path, seed=False) as second:
                f = SqliteBlobFixture(second)
                await activate(second, f, "B", 2)
                with closing(sqlite3.connect(path)) as conn:
                    store = SQLiteExecutionStore(conn)
                    checkpoint = await store.load(execution)
                    restored = InvocationGraph.model_validate_json(checkpoint.blob)
                    self.assertIsNone(restored.records[invocation].continuation)
                    async with second[1].transaction("find-open") as scope:
                        rows = await f.catalog._scopes.access.all(scope,
                            "SELECT pin FROM probe_pins WHERE owner=? AND closed=0", (owner,))
                    self.assertEqual(len(rows), 1)
                    pin = rows[0]["pin"]
                    version, ref, holder = await acquire(second, f, pin, owner)
                    self.assertEqual(version, "A")
                    async with f.catalog.guard(ref):
                        self.assertTrue(await f.holders.is_held(ref, holder))
                        self.assertEqual(await f.backend.read_verified(ref, max_bytes=ref.nbytes), initial_bytes)
                    # Fixture drives RESPONSE checkpoint directly, without executing an engine node.
                    claim = await store.claim(execution, "new-worker", 60)
                    restored.records[invocation].status = InvocationStatus.SUCCEEDED
                    restored.response = json.dumps({"ok": True, "data": {"text": "done"}, "error": None})
                    await store.checkpoint(claim, checkpoint.revision, restored.checkpoint_status(),
                                           restored.model_dump_json().encode())

            async with live_database(path, seed=False) as third:
                f = SqliteBlobFixture(third)
                with closing(sqlite3.connect(path)) as conn:
                    terminal = await SQLiteExecutionStore(conn).load(execution)
                    self.assertEqual(terminal.status, ExecutionResponseStatus.COMPLETED)
                    ended = InvocationGraph.model_validate_json(terminal.blob)
                    self.assertEqual(ended.execution_id, execution)
                    self.assertIsNotNone(ended.response)
                for expected_count in (1, 0):
                    async with third[1].transaction("find-release") as scope:
                        rows = await f.catalog._scopes.access.all(scope,
                            "SELECT pin FROM probe_pins WHERE owner=? AND closed=0", (owner,))
                    self.assertEqual(len(rows), expected_count)
                    for row in rows:
                        _, ref, holder = await acquire(third, f, row["pin"], owner)
                        async with third[1].transaction("release") as scope:
                            async with f.catalog._scopes.bind(scope):
                                await f.holders.release(ref, holder)
                                await third[0].conn.execute("UPDATE probe_pins SET closed=1 WHERE pin=?", (row["pin"],))
                        self.assertFalse(await f.holders.is_held(ref, holder))
