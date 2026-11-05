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

    async def test_guarded_admission_revocation_first_opens_zero_files(self):
        await self.exercise(shared=True, guarded_admission=True, revoke_first=True)

    async def test_guarded_admission_read_first_closes_before_release(self):
        await self.exercise(shared=True, guarded_admission=True)

    async def test_independent_checkpoint_between_guarded_check_and_open(self):
        await self.exercise(shared=False, separate_check_gap=True)

    async def exercise(self, *, shared, guarded_admission=False, revoke_first=False, separate_check_gap=False):
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
            prechecked, continue_to_guard = asyncio.Event(), asyncio.Event()
            opened = []
            open_calls = []
            paths = {f.backend._path(ref), f.backend._path(next_ref)}
            opens = Path.open

            def controlled_open(path, *args, **kwargs):
                if path in paths:
                    open_calls.append(path)
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
                if revoke_first:
                    prechecked.set()
                    await continue_to_guard.wait()
                async with f.catalog.guard(artifact):
                    if not await f.holders.is_held(artifact, holder):
                        raise ValueError("missing hold")
                    if separate_check_gap:
                        self.assertNotEqual((await store.load(execution)).status, InvocationStatus.FAILED)
                        prechecked.set()
                        await continue_to_guard.wait()
                    if guarded_admission:
                        scopes = f.catalog._scopes
                        async with scopes.read_scope() as scope:
                            state = await scopes.access.one(scope, "SELECT status FROM dag_executions WHERE execution_id=?",
                                                           (execution,))
                        if state is None or state["status"] == InvocationStatus.FAILED.value:
                            raise ValueError("revoked inside guard")
                    return await f.backend.read_verified(artifact, max_bytes=artifact.nbytes)

            async def cleanup():
                async with other.catalog.guard(ref):
                    self.assertTrue(opened[0].closed)
                    for artifact in (ref, next_ref):
                        await other.holders.release(artifact, holder)

            async def terminal():
                await store.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())

            with patch.object(Path, "open", controlled_open):
                if separate_check_gap:
                    async with asyncio.TaskGroup() as tasks:
                        stale = tasks.create_task(read_if_live(ref))
                        try:
                            await asyncio.wait_for(prechecked.wait(), 5)
                            await terminal()
                            self.assertEqual((await store.load(execution)).status, InvocationStatus.FAILED)
                            self.assertTrue(await observer.holders.is_held(ref, holder))
                            self.assertEqual(open_calls, [])
                        finally:
                            finish.set()
                            continue_to_guard.set()
                    self.assertEqual(stale.result(), b"first")
                    self.assertEqual(open_calls, [f.backend._path(ref)])
                    self.assertTrue(opened[0].closed)
                    return
                if revoke_first:
                    async def stale_worker():
                        with self.assertRaisesRegex(ValueError, "revoked inside guard"):
                            await read_if_live(ref)

                    async with asyncio.TaskGroup() as tasks:
                        tasks.create_task(stale_worker())
                        try:
                            await asyncio.wait_for(prechecked.wait(), 5)
                            await terminal()
                            self.assertEqual((await store.load(execution)).status, InvocationStatus.FAILED)
                            self.assertTrue(await observer.holders.is_held(ref, holder))
                        finally:
                            finish.set()
                            continue_to_guard.set()
                    self.assertEqual(open_calls, [])
                    return
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
            self.assertEqual(open_calls, [f.backend._path(ref)])
            if shared:
                await terminal()
                with self.assertRaisesRegex(ValueError, "execution closed"):
                    await read_if_live(next_ref)
                await cleanup()
            for artifact in (ref, next_ref):
                self.assertFalse(await other.holders.is_held(artifact, holder))
