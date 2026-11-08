"""F6 restart boundaries across independent DAG and Pack databases."""
import asyncio
import sqlite3
import threading
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.application.engine.contracts.invocation.inputWait import Failed
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, OperationHolder, PinHolder
from app.db.repositories.sqlite.worldPack.executionPins import PackClosed
from tests.dag_typing.invocations import test_world_calls as dag

from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from tests.spatial_pack.test_execution_pins import ExecutionPinFixture


class ExecutionFinalityReopenTests(ExecutionPinFixture):
    async def reopen_stores(self):
        await self.stack.aclose()
        self.dag.db.close()
        connection = self.enterContext(closing(sqlite3.connect(self.path.with_name("dag.db"))))
        self.dag = SQLiteExecutionStore(connection)
        await self.connect_pack(False)

    async def test_completed(self):
        await self.exercise(False)

    async def test_failed(self):
        await self.exercise(True)

    async def exercise(self, failed):
        key = dag.ExecutionId("f6")
        first = replace(self.intent, execution_id=key, pin_id="f6-a")
        second = replace(first, pin_id="f6-b", invocation_id="reader")
        expected_bytes = Path(__file__).with_name("fixtures").joinpath("retention-shard.tlv").read_bytes()
        opened, unblock = threading.Event(), threading.Event()
        events = []
        original_open = Path.open
        pins = self.pins
        shard = self.shard

        @contextmanager
        def physical_open(path, *args, **kwargs):
            with original_open(path, *args, **kwargs) as stream:
                if path.name != shard.content_hash:
                    yield stream
                    return
                events.append("open")
                opened.set()
                if failed and not unblock.wait(10):
                    raise TimeoutError("child A did not run")
                yield stream
            events.append("stream closed")

        class Children(dag.Transform):
            async def execute(child, input):
                if input.value == "ok":
                    await pins.acquire(second)
                    self.assertEqual(await pins.read_shard(second, shard), expected_bytes)
                if failed and input.value == "failed":
                    self.assertTrue(await asyncio.to_thread(opened.wait, 10))
                    try:
                        return await super().execute(input)
                    except dag.PythonNodeError:
                        events.append("child A failed")
                        raise
                    finally:
                        unblock.set()
                return await super().execute(input)

        original_resume = dag.Group.resume

        async def join(group, state, event):
            result = await original_resume(group, state, event)
            await pins.acquire(first)
            if failed:
                raise dag.PythonNodeError(dag.TestNodeError(item_id=1))
            return result

        def engine():
            return dag.runtime(dag.Group, store=self.dag, pack_closer=self.pins, transform=Children, workers=3)

        options = dict(max_passes=1, options=dag.LLMExecutionOptions(
            player_message="", language="ru", repair_iterations=0, repair_mode=dag.RepairMode.MAXIMUM))
        with (patch.object(dag.Group, "resume", join), patch.object(Path, "open", physical_open),
              patch.object(self.dag, "record_stop_intent", side_effect=dag.Crash), self.assertRaises(dag.Crash)):
            await engine().run(key, dag.TaskType.INTENT_DETECTION, **options)
        self.assertEqual(events, ["open", "child A failed", "stream closed"] if failed else ["open", "stream closed"])
        checkpoint = await self.dag.load(key)
        self.assertIsNone(checkpoint.stop_intent)
        await self.reopen_stores()
        self.assertEqual(await self.dag.load(key), checkpoint)
        pins = self.pins
        version_b = await self.publish("b", 2)
        owner_b = ArtifactRetentionHolder(artifact=version_b)
        # Finish the fixture publications' transfers to their manifest owners.
        for holder in await self.fixture.holders.holders(shard):
            if isinstance(holder, OperationHolder):
                async with self.bundle[1].transaction(holder.lease.operation_id) as scope:
                    await self.fixture.holders.handoff(scope, holder.lease, (), (self.root, shard))
        with (patch.object(dag.Group, "resume", join), patch.object(pins, "close", side_effect=dag.Crash),
              self.assertRaises(dag.Crash)):
            await engine().resume(key, **options)
        intent = (await self.dag.load(key)).stop_intent
        self.assertIsInstance(intent.outcome, dag.FailedOutcome if failed else dag.CompletedOutcome)
        self.assertIsNone(await pins.read_closed(intent))
        await self.reopen_stores()
        close = self.pins.close
        receipts = []

        async def lose_reply(command):
            receipts.append(await close(command))
            events.append("CLOSED")
            raise dag.Crash()

        with patch.object(dag.CheckpointCodec, "restore", side_effect=AssertionError("restored outputs")):
            with patch.object(self.pins, "close", lose_reply), self.assertRaises(dag.Crash):
                await engine().resume(key, **options)
            await self.reopen_stores()
            self.assertEqual(await self.pins.close(intent), receipts[0])
            self.assertIsNone((await self.dag.load(key)).final_revision)
            for pin in (first, second):
                self.assertTrue(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=pin.pin_id)))
            with patch.object(Path, "open", autospec=True) as physical, self.assertRaises(PackClosed):
                await self.pins.read_shard(second, shard)
            self.assertEqual(physical.call_count, 0)
            finalize = self.dag.finalize

            async def after_final(*args):
                await finalize(*args)
                events.append("finalized")
                raise dag.Crash()

            with patch.object(self.dag, "finalize", after_final), self.assertRaises(dag.Crash):
                await engine().resume(key, **options)
            await self.reopen_stores()
            final = await self.dag.load(key)
            self.assertEqual((final.stop_intent, final.final_revision, final.revision),
                             (intent, intent.stop_revision + 1, intent.stop_revision + 1))
            expected = (Failed(intent.outcome.diagnostic) if failed else
                        dag.TypeAdapter(dag.ResolveResult[dag.Text]).validate_json(intent.outcome.result_json))
            self.assertEqual(await engine().resume(key, **options), expected)
            release = self.fixture.holders._release_pin

            async def interrupt(scope, artifact, holder):
                await release(scope, artifact, holder)
                if holder.pin_id == second.pin_id:
                    raise dag.Crash()
                events.append("release A")

            with patch.object(self.fixture.holders, "_release_pin", interrupt), self.assertRaises(dag.Crash):
                await self.pins.cleanup(intent)
            await self.reopen_stores()
            for pin, held in ((first, False), (second, True)):
                self.assertEqual(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=pin.pin_id)), held)
            for _ in range(2):
                self.assertEqual(await engine().resume(key, **options), expected)
                await self.pins.cleanup(intent)
                self.assertEqual(await self.pins.read_closed(intent), receipts[0])
                self.assertFalse(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=second.pin_id)))
        self.assertLess(events.index("stream closed"), events.index("CLOSED"))
        self.assertLess(events.index("CLOSED"), events.index("finalized"))
        self.assertLess(events.index("finalized"), events.index("release A"))
        owner_a = ArtifactRetentionHolder(artifact=self.manifest)
        for child in (self.root, shard):
            await self.fixture.holders.release(child, owner_a)
        self.assertEqual(await self.fixture.holders.holders(shard), (owner_b,))
        gc = await self.fixture.service.collect("f6-gc", (self.root, shard))
        self.assertEqual(gc.retained, (self.root, shard))
        await self.reopen_stores()
        reader = OpenWaterBlobReader(self.fixture.service._registry, self.fixture.catalog, self.fixture.holders)
        self.assertEqual(await reader.read_shard(shard, owner_b), expected_bytes)
