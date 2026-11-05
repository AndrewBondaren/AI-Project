"""Execution-scoped retention probe using a real next_pass and fixture Pack bindings."""
import json
import sqlite3
from contextlib import closing
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from uuid import NAMESPACE_URL, uuid5

from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import ExecutionResponseStatus, InvocationGraph, InvocationStatus
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from tests.dag_typing.invocations.test_world_calls import runtime
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database
from tests.spatial_pack.test_pin_binding_replay import acquire, activate


class ProbeRead(StrEnum):
    BASE = "base"
    FOLLOWUP = "followup"
    LATE = "late"


def probe_pin(owner: str, read: ProbeRead) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps([owner, read.value])))


class PinPassCompletionTests(IsolatedAsyncioTestCase):
    async def test_pin_survives_next_pass_until_execution_response_is_saved(self):
        execution = ExecutionId("scenario")
        _, plan = runtime()
        coord = InvocationCoordinator.create(plan, execution, PlanRevision("1"), plan.invocation_root, 16, None)
        graph = coord.graph
        invocation = graph.root
        owner = json.dumps([execution, invocation])
        reads = (ProbeRead.BASE, ProbeRead.FOLLOWUP)
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
                for read in ProbeRead:
                    await f.stager.stage(anchor, probe_pin(owner, read).encode())
                await activate(first, f, "A", 1)
                with closing(sqlite3.connect(path)) as conn:
                    store = SQLiteExecutionStore(conn)
                    await store.create(execution, graph.model_dump_json().encode())
                    claim = await store.claim(execution, "worker", 60)
                    record = graph.records[invocation]
                    record.continuation = json.dumps({read.value: probe_pin(owner, read) for read in reads})
                    await store.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())
                    first_read = await acquire(first, f, probe_pin(owner, ProbeRead.BASE), owner)
                    self.assertEqual(first_read[0], "A")
                    async with f.catalog.guard(first_read[1]):
                        initial_bytes = await f.backend.read_verified(first_read[1], max_bytes=first_read[1].nbytes)
                    self.assertEqual(decode_manifest(initial_bytes).world_map_cells, 1)
                    await activate(first, f, "B", 2)
                    second_read = await acquire(first, f, probe_pin(owner, ProbeRead.FOLLOWUP), owner)
                    self.assertEqual(second_read[0], "B")
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
                await activate(second, f, "C", 3)
                with closing(sqlite3.connect(path)) as conn:
                    store = SQLiteExecutionStore(conn)
                    checkpoint = await store.load(execution)
                    restored = InvocationGraph.model_validate_json(checkpoint.blob)
                    self.assertIsNone(restored.records[invocation].continuation)
                    async with second[1].transaction("find-open") as scope:
                        rows = await f.catalog._scopes.access.all(scope,
                            "SELECT pin FROM probe_pins WHERE owner=? AND closed=0", (owner,))
                    self.assertCountEqual([row["pin"] for row in rows], [probe_pin(owner, read) for read in reads])
                    for read, expected, cells in ((ProbeRead.FOLLOWUP, "B", 2), (ProbeRead.BASE, "A", 1)):
                        version, ref, holder = await acquire(second, f, probe_pin(owner, read), owner)
                        self.assertEqual(version, expected)
                        async with f.catalog.guard(ref):
                            self.assertTrue(await f.holders.is_held(ref, holder))
                            data = await f.backend.read_verified(ref, max_bytes=ref.nbytes)
                            self.assertEqual(decode_manifest(data).world_map_cells, cells)
                            if read is ProbeRead.BASE:
                                self.assertEqual(data, initial_bytes)
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
                async def require_live():
                    with closing(sqlite3.connect(path)) as conn:
                        cp = await SQLiteExecutionStore(conn).load(execution)
                        if cp.status is ExecutionResponseStatus.COMPLETED:
                            raise ValueError("completed execution")

                for expected_count in (2, 0):
                    for read in (ProbeRead.BASE, ProbeRead.LATE):
                        with self.assertRaisesRegex(ValueError, "completed execution"):
                            await acquire(third, f, probe_pin(owner, read), owner, check_owner=require_live)
                    async with third[1].transaction("find-release") as scope:
                        rows = await f.catalog._scopes.access.all(scope,
                            "SELECT pin, publication_id FROM probe_pins WHERE owner=? AND closed=0", (owner,))
                    self.assertEqual(len(rows), expected_count)
                    for row in rows:
                        async with third[1].transaction("release") as scope:
                            refs = await f.catalog._scopes.access.one(scope, """SELECT m.artifact_id AS manifest,
                                t.artifact_id AS token FROM world_publications p JOIN artifact_catalog m
                                ON m.content_hash=p.pack_hash JOIN artifact_catalog t ON t.content_hash=?
                                WHERE p.publication_id=? AND m.format_key='test.blob' AND m.kind='blob'
                                AND m.format_version=1 AND (t.format_key,t.kind,t.format_version)
                                =(m.format_key,m.kind,m.format_version)""",
                                (sha256(row["pin"].encode()).hexdigest(), row["publication_id"]))
                            ref = await f.catalog._by_id(scope, refs["manifest"])
                            holder = ArtifactRetentionHolder(artifact=await f.catalog._by_id(scope, refs["token"]))
                            async with f.catalog._scopes.bind(scope):
                                await f.holders.release(ref, holder)
                                await third[0].conn.execute("UPDATE probe_pins SET closed=1 WHERE pin=?", (row["pin"],))
                        self.assertFalse(await f.holders.is_held(ref, holder))
                async with third[1].transaction("verify-late") as scope:
                    access = f.catalog._scopes.access
                    self.assertIsNone(await access.one(scope, "SELECT pin FROM probe_pins WHERE pin=?",
                                                      (probe_pin(owner, ProbeRead.LATE),)))
                    events = await access.all(scope, """SELECT event_id FROM artifact_holder_events
                        WHERE retained_artifact_id IN (SELECT artifact_id FROM artifact_catalog WHERE content_hash=?)""",
                        (sha256(probe_pin(owner, ProbeRead.LATE).encode()).hexdigest(),))
                    self.assertEqual(events, [])
