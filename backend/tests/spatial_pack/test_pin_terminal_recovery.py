"""Probe durable cancellation and idempotent Pack cleanup in the same SQLite database."""
import sqlite3
from dataclasses import replace
from unittest.mock import patch
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from uuid import UUID

from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, ExecutionId, InvocationId, NodeId, PlanInstanceId, PlanRevision,
)
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationRecord, InvocationStatus, RegisteredContract
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database
from tests.spatial_pack.test_pin_binding_replay import acquire, activate
from tests.spatial_pack.test_pin_intent_checkpoint import ProbePinIntent
from tests.spatial_pack.test_execution_pins import ExecutionPinFixture
from app.dataModel.artifacts.lifecycle.holders import PinHolder
from app.db.repositories.sqlite.worldPack.executionPins import PackIdentityConflict, PackIntentUnavailable
from app.application.engine.contracts.invocation.executionStore import CloseReceipt


class FinalizedCleanupTests(ExecutionPinFixture):
    async def test_finalized_without_matching_local_receipt_preserves_hold(self):
        command = await self.stop()
        receipt = CloseReceipt(command.store_id, command.execution_id, command.stop_revision)
        await self.dag.finalize(self.claim, command.stop_revision, receipt)
        with self.assertRaises(PackIdentityConflict):
            await self.pins.cleanup(command)
        async with self.bundle[0].transaction():
            await self.bundle[0].conn.execute("INSERT INTO pack_execution_closed VALUES (?,?,?)",
                (str(command.store_id), command.execution_id, command.stop_revision + 1))
        with self.assertRaises(PackIdentityConflict):
            await self.pins.cleanup(command)
        self.assertTrue(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=self.intent.pin_id)))

    async def test_interrupted_cleanup_reopens_both_stores(self):
        second = replace(self.intent, pin_id="pin-b", logical_read_key="other")
        await self.pins.acquire(second)
        await self.dag.create("foreign", b"checkpoint")
        foreign = replace(self.intent, execution_id="foreign", pin_id="foreign-pin")
        await self.pins.acquire(foreign)
        command = await self.stop()
        receipt = await self.pins.close(command)
        with self.assertRaises(PackIdentityConflict):
            await self.pins.cleanup(command)
        await self.dag.finalize(self.claim, command.stop_revision, receipt)
        with patch.object(self.dag, "load", side_effect=OSError("offline")):
            with self.assertRaises(PackIntentUnavailable):
                await self.pins.cleanup(command)
        release = self.fixture.holders._release_pin

        async def interrupt(scope, artifact_id, holder):
            await release(scope, artifact_id, holder)
            if holder.pin_id == second.pin_id:
                raise InterruptedError("second transaction")

        with patch.object(self.fixture.holders, "_release_pin", interrupt):
            with self.assertRaises(InterruptedError):
                await self.pins.cleanup(command)
        await self.stack.aclose()
        self.dag.db.close()
        db = self.enterContext(closing(sqlite3.connect(self.path.with_name("dag.db"))))
        self.dag = SQLiteExecutionStore(db)
        await self.connect_pack(False)
        held = self.fixture.holders.is_held
        self.assertFalse(await held(self.manifest, PinHolder(pin_id=self.intent.pin_id)))
        self.assertTrue(await held(self.manifest, PinHolder(pin_id=second.pin_id)))
        for _ in range(2):
            await self.pins.cleanup(command)
            self.assertEqual(await self.pins.read_closed(command), receipt)
            self.assertFalse(await held(self.manifest, PinHolder(pin_id=second.pin_id)))
            self.assertTrue(await held(self.manifest, PinHolder(pin_id=foreign.pin_id)))
            async with self.bundle[0].conn.execute(
                "SELECT state FROM pack_execution_pins WHERE store_id=? AND execution_id=?",
                (str(command.store_id), command.execution_id),
            ) as cursor:
                self.assertEqual([row[0] for row in await cursor.fetchall()], ["RELEASED", "RELEASED"])


class PinTerminalRecoveryTests(IsolatedAsyncioTestCase):
    async def test_cancel_precedes_acquire(self):
        await self.probe(open_pin=False)

    async def test_cancel_committed_before_cleanup_and_restart(self):
        await self.probe(open_pin=True)

    async def probe(self, open_pin):
        execution, invocation = ExecutionId("exec"), InvocationId("inv")
        intent = ProbePinIntent(pin_id=UUID(int=29), world_uid="w1")
        pin = str(intent.pin_id)
        owner = '["exec","inv"]'
        record = InvocationRecord(execution_id=execution, invocation_id=invocation, node_id=NodeId("probe"),
                                  plan_instance_id=PlanInstanceId("plan"), contract_id=ContractId("input"),
                                  version=ContractVersion("1"), status=InvocationStatus.RUNNING,
                                  plan_revision=PlanRevision("r"), continuation=intent.model_dump_json(),
                                  state_contract=(ContractId("intent"), ContractVersion("1")))
        contract = RegisteredContract(node_id=record.node_id, contract_id=record.contract_id, version=record.version,
                                      continuation=record.state_contract, input_wait=None)
        graph = InvocationGraph(execution_id=execution, root=invocation, revision=record.plan_revision,
                                registry=(contract,), records={invocation: record})
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "world.sqlite")
            async with live_database(path) as first:
                fixture = SqliteBlobFixture(first)
                async with first[0].transaction():
                    await first[0].conn.execute("""CREATE TABLE probe_pins(
                        pin TEXT PRIMARY KEY, owner TEXT NOT NULL, publication_id TEXT, closed INTEGER NOT NULL)""")
                async with first[1].transaction("init") as scope:
                    await first[2].initialize(scope, "w1")
                anchors = await fixture.open("anchors")
                await fixture.stager.stage(anchors, pin.encode())
                await activate(first, fixture, "A", 1)
                with closing(sqlite3.connect(path)) as connection:
                    dag = SQLiteExecutionStore(connection)
                    await dag.create(execution, graph.model_dump_json().encode())
                    claim = await dag.claim(execution, "worker", 60)
                    rev = await dag.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())
                    if open_pin:
                        await acquire(first, fixture, pin, owner)
                    graph.records[invocation].status = InvocationStatus.CANCELLED
                    graph.cancellation = "execution cancelled"
                    self.assertTrue(await dag.cancel(execution, rev, graph.model_dump_json().encode()))
                    # End the session before any Pack cleanup.

            async with live_database(path, seed=False) as second:
                fixture = SqliteBlobFixture(second)
                with closing(sqlite3.connect(path)) as connection:
                    dag = SQLiteExecutionStore(connection)

                    async def intent_from_terminal():
                        cp = await dag.load(execution)
                        restored = InvocationGraph.model_validate_json(cp.blob)
                        child = restored.records[invocation]
                        self.assertEqual((restored.execution_id, child.execution_id, child.invocation_id),
                                         (execution, execution, invocation))
                        self.assertEqual(cp.status, InvocationStatus.CANCELLED)
                        self.assertEqual(child.status, InvocationStatus.CANCELLED)
                        self.assertIsNotNone(restored.cancellation)
                        return ProbePinIntent.model_validate_json(child.continuation)

                    async def require_live_owner():
                        if (await dag.load(execution)).status == InvocationStatus.CANCELLED:
                            raise ValueError("cancelled owner")

                    # Even before recovery has installed CLOSED, a delayed attempt must refuse.
                    with self.assertRaisesRegex(ValueError, "cancelled owner"):
                        await acquire(second, fixture, pin, owner, check_owner=require_live_owner)
                    for attempt in range(2):
                        restored = await intent_from_terminal()
                        self.assertEqual(restored, intent)
                        async with second[1].transaction("cleanup") as scope:
                            access = fixture.catalog._scopes.access
                            row = await access.one(scope, "SELECT * FROM probe_pins WHERE pin=?", (str(restored.pin_id),))
                            if row is None:
                                self.assertFalse(open_pin)
                                await second[0].conn.execute("INSERT INTO probe_pins VALUES (?,?,NULL,1)", (pin, owner))
                            else:
                                self.assertEqual(row["owner"], owner)
                                self.assertEqual(bool(row["closed"]), bool(attempt))
                                if row["closed"]:
                                    continue
                                self.assertTrue(open_pin)
                                refs = await access.one(scope, """SELECT m.artifact_id AS manifest, t.artifact_id AS token
                                    FROM world_publications p JOIN artifact_catalog m ON p.pack_hash=m.content_hash
                                    JOIN artifact_catalog t ON t.content_hash=?
                                    WHERE p.publication_id=? AND m.format_key=t.format_key AND m.kind=t.kind
                                    AND m.format_version=t.format_version AND m.kind='blob'
                                    AND m.format_key='test.blob' AND m.format_version=1""",
                                    (sha256(pin.encode()).hexdigest(), row["publication_id"]))
                                manifest = await fixture.catalog._by_id(scope, refs["manifest"])
                                holder = ArtifactRetentionHolder(artifact=await fixture.catalog._by_id(scope, refs["token"]))
                                async with fixture.catalog._scopes.bind(scope):
                                    self.assertTrue(await fixture.holders.is_held(manifest, holder))
                                    await fixture.holders.release(manifest, holder)
                                    self.assertFalse(await fixture.holders.is_held(manifest, holder))
                                await second[0].conn.execute("UPDATE probe_pins SET closed=1 WHERE pin=?", (pin,))
                with self.assertRaisesRegex(ValueError, "foreign or closed"):
                    await acquire(second, fixture, pin, owner)
