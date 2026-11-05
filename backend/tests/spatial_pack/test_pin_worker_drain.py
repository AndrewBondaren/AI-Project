"""Controlled terminal/read interleaving; terminal admission is a fixture adapter."""
import asyncio
import sqlite3
import threading
from contextlib import AsyncExitStack, closing
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, OperationHolder
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import InvocationStatus
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from tests.dag_typing.invocations.test_world_calls import runtime
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database


class PinWorkerDrainTests(IsolatedAsyncioTestCase):
    async def test_shared_sqlite_serializes_terminal_after_read(self):
        await self.exercise(shared=True)

    async def test_independent_checkpoint_can_commit_during_read(self):
        await self.exercise(shared=False)

    async def exercise(self, *, shared):
        async with AsyncExitStack() as stack:
            pack = await stack.enter_async_context(live_database())
            competitor = await stack.enter_async_context(live_database(pack[0].path, seed=False))
            observer = SqliteBlobFixture(await stack.enter_async_context(live_database(pack[0].path, seed=False)))
            dag_db = pack if shared else await stack.enter_async_context(live_database())
            conn = stack.enter_context(closing(sqlite3.connect(dag_db[0].path, timeout=0)))
            store = SQLiteExecutionStore(conn)
            execution = ExecutionId("worker-probe")
            _, plan = runtime()
            graph = InvocationCoordinator.create(plan, execution, PlanRevision("1"), plan.invocation_root, 16, None).graph
            await store.create(execution, graph.model_dump_json().encode())
            claim = await store.claim(execution, "worker", 60)
            graph.failure = "probe failure"
            graph.records[graph.root].status = InvocationStatus.FAILED

            f, other = SqliteBlobFixture(pack), SqliteBlobFixture(competitor)
            lease = await f.open("stage")
            ref = await f.stager.stage(lease, b"first")
            next_ref = await f.stager.stage(lease, b"second")
            holder = ArtifactRetentionHolder(artifact=await f.stager.stage(lease, b"pin-token"))
            await f.service.finish_preparation(lease, (ref, next_ref, holder.artifact))
            for artifact in (ref, next_ref):
                await f.holders.acquire(artifact, holder)
                await f.holders.release(artifact, OperationHolder(lease=lease))

            entered, finish, cleanup_attempt = threading.Event(), threading.Event(), threading.Event()
            opened = []
            opens = Path.open

            def controlled_open(path, *args, **kwargs):
                stream = opens(path, *args, **kwargs)
                if path == f.backend._path(ref):
                    opened.append(stream)
                    entered.set()
                    if not finish.wait(6):
                        stream.close()
                        raise TimeoutError("read barrier")
                return stream

            async def read_if_live(artifact):
                if (await store.load(execution)).status == InvocationStatus.FAILED:
                    raise ValueError("execution closed")
                async with f.catalog.guard(artifact):
                    if not await f.holders.is_held(artifact, holder):
                        raise ValueError("missing hold")
                    return await f.backend.read_verified(artifact, max_bytes=artifact.nbytes)

            async def cleanup():
                async with other.catalog.guard(ref):
                    self.assertTrue(opened[0].closed)
                    for artifact in (ref, next_ref):
                        await other.holders.release(artifact, holder)

            async def terminal():
                await store.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())

            with patch.object(Path, "open", controlled_open):
                async with asyncio.TaskGroup() as tasks:
                    first = tasks.create_task(read_if_live(ref))
                    try:
                        self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                        self.assertFalse(opened[0].closed)
                        if shared:
                            with self.assertRaises(sqlite3.OperationalError) as busy:
                                await terminal()
                            self.assertEqual(busy.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
                            self.assertNotEqual((await store.load(execution)).status, InvocationStatus.FAILED)
                        else:
                            await terminal()
                            await competitor[0].conn.set_trace_callback(
                                lambda sql: cleanup_attempt.set() if sql == "BEGIN IMMEDIATE" else None)
                            pending = tasks.create_task(cleanup())
                            self.assertTrue(await asyncio.to_thread(cleanup_attempt.wait, 5))
                            self.assertFalse(pending.done())
                            with self.assertRaisesRegex(ValueError, "execution closed"):
                                await read_if_live(next_ref)
                        self.assertTrue(await observer.holders.is_held(ref, holder))
                    finally:
                        finish.set()
            self.assertEqual(first.result(), b"first")
            self.assertTrue(opened[0].closed)
            if shared:
                await terminal()
                with self.assertRaisesRegex(ValueError, "execution closed"):
                    await read_if_live(next_ref)
                await cleanup()
            for artifact in (ref, next_ref):
                self.assertFalse(await other.holders.is_held(artifact, holder))
