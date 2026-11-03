import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException

from app.application.engine.contracts.invocation.inputWait import (
    Failed, InputConflict, InputReceived, InputWaitContract, ResumeInput, Waiting, WaitInput, WaitSpec,
)
from app.dataModel.engine.dag.identity import WaitId
from app.dataModel.engine.dag.invocations.inputWait import InteractionBinding, InteractionOwner
from tests.dag_typing.invocations import test_world_calls as f


CHOICE = InputWaitContract(f.ContractId("choice"), f.ContractVersion("1"), f.Count, f.Text)
KEY = f.ExecutionId("interactive")
OPTIONS = f.LLMExecutionOptions(player_message="", language="ru", repair_iterations=0, repair_mode=f.RepairMode.MAXIMUM)


class Ask(f.CountCaller):
    async def start(self, input):
        return WaitInput(WaitSpec(WaitId("pick"), CHOICE, "question", f.Text(text="Choose"), 3), input)

    async def resume(self, state, event):
        assert isinstance(event, InputReceived)
        return f.Complete(event.get(CHOICE))


class AskAndFormat(f.Pipeline):
    async def start(self, input):
        return f.CallGroup((f.COUNT.request(f.CallKey("ask"), input),
                            f.FORMAT.request(f.CallKey("format"), f.Count(value=4))), f.Payload())

    async def resume(self, state, event):
        count = event.get(f.CallKey("ask"), f.COUNT)
        formatted = event.get(f.CallKey("format"), f.FORMAT)
        return f.Complete(f.Text(text=f"{count.output.value}/{formatted.output.text}"))


class Session:
    def __init__(self, session):
        self.owner = InteractionOwner(world_uid="world", player_uid="player", session_uid=session)

    def bind(self, reference, identity, step):
        return InteractionBinding(owner=self.owner, reference=reference, revision=3, policy_evidence="positive")

    def authorize(self, binding, payload):
        if binding.policy_evidence != "positive" or payload.value < 0:
            raise PermissionError("choice is forbidden")


class InputWaitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "interaction.sqlite"
        schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(schema.read_text("utf-8"))

    def engine(self, db, session="a"):
        return f.runtime(store=f.SQLiteExecutionStore(db), counter=Ask, counter_wait=CHOICE, interaction=Session(session))

    async def start(self, db):
        return await self.engine(db).run(KEY, f.TaskType.INTENT_DETECTION, max_passes=1, options=OPTIONS)

    async def test_http_reopens_sqlite_and_replays_receipt(self):
        app = FastAPI()

        @app.post("/start")
        async def start():
            with closing(sqlite3.connect(self.path)) as db:
                waiting = await self.start(db)
                self.assertIsInstance(waiting, Waiting)
                pending, = waiting.pending
                return {"wait_id": pending.wait_id, "revision": pending.expected_revision,
                        "question": pending.intermediate.text}

        @app.post("/answer")
        async def answer(request: ResumeInput[f.Count], session: str = Header()):
            with closing(sqlite3.connect(self.path)) as db:
                try:
                    delivery = await self.engine(db, session).resume_input(KEY, request, max_passes=1, options=OPTIONS)
                except PermissionError as exc:
                    raise HTTPException(403) from exc
                except InputConflict as exc:
                    raise HTTPException(409) from exc
                return {"receipt": delivery.receipt, "result": delivery.result}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            self.assertEqual((await client.post("/start")).json(), {"wait_id": "pick", "revision": 3, "question": "Choose"})
            request = {"wait_id": "pick", "request_id": "first", "expected_revision": 3, "payload": {"value": 5}}
            with closing(sqlite3.connect(self.path)) as db:
                store = f.SQLiteExecutionStore(db)
                before = await store.load(KEY)
                self.assertEqual(before.status, "WAITING_INPUT")
                graph = f.InvocationGraph.model_validate_json(before.blob)
                self.assertEqual(graph.records[graph.root].status, "WAITING_CALLS")
                self.assertIsNone(graph.response)
                for session, change, code in (("b", {}, 403), ("a", {"expected_revision": 2}, 409),
                                              ("a", {"wait_id": "later"}, 409), ("a", {"payload": {"value": -1}}, 403)):
                    reply = await client.post("/answer", headers={"session": session}, json=request | change)
                    self.assertEqual(reply.status_code, code)
                    self.assertEqual(await store.load(KEY), before)
            first = await client.post("/answer", headers={"session": "a"}, json=request)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json()["receipt"]["revision"], 4)
            self.assertIn("count=5", first.text)
            replay = await client.post("/answer", headers={"session": "a"}, json=request)
            self.assertEqual(first.json(), replay.json())
            conflict = await client.post("/answer", headers={"session": "a"}, json=request | {"payload": {"value": 6}})
            self.assertEqual(conflict.status_code, 409)

    async def test_single_worker_finishes_ready_sibling_before_waiting(self):
        with closing(sqlite3.connect(self.path)) as db:
            store = f.SQLiteExecutionStore(db)
            engine = f.runtime(entry=AskAndFormat, store=store, counter=Ask, counter_wait=CHOICE, interaction=Session("a"))
            waiting = await engine.run(KEY, f.TaskType.INTENT_DETECTION, max_passes=1, options=OPTIONS)
            self.assertIsInstance(waiting, Waiting)
            graph = f.InvocationGraph.model_validate_json((await store.load(KEY)).blob)
            self.assertEqual(next(r for r in graph.records.values() if r.node_id == f.FORMAT.node_id).status, "SUCCEEDED")
            request = ResumeInput[f.Count](wait_id=WaitId("pick"), request_id="join", expected_revision=3, payload=f.Count(value=7))
            delivery = await engine.resume_input(KEY, request, max_passes=1, options=OPTIONS)
            self.assertEqual(delivery.result.data, f.Text(text="7/count=4"))

    async def test_restart_after_accept_before_continuation(self):
        request = ResumeInput[f.Count](wait_id=WaitId("pick"), request_id="first", expected_revision=3, payload=f.Count(value=7))
        with closing(sqlite3.connect(self.path)) as db:
            await self.start(db)
            receipt = await self.engine(db).accept_input(KEY, request)
        with closing(sqlite3.connect(self.path)) as db:
            delivery = await self.engine(db).resume_input(KEY, request, max_passes=1, options=OPTIONS)
            self.assertEqual(delivery.receipt, receipt)
            self.assertIn("count=7", str(delivery.result))

    async def test_cancel_waiting_execution_and_reject_late_reply(self):
        with closing(sqlite3.connect(self.path)) as db:
            await self.start(db)
            engine = self.engine(db)
            await engine.cancel_execution(KEY)
            self.assertIsInstance(await engine.resume(KEY, max_passes=1, options=OPTIONS), Failed)
            saved = await f.SQLiteExecutionStore(db).load(KEY)
            self.assertEqual(saved.status, "CANCELLED")
            self.assertTrue(all(r.status == "CANCELLED" for r in f.InvocationGraph.model_validate_json(saved.blob).records.values()))
            with self.assertRaises(InputConflict):
                await engine.accept_input(KEY, ResumeInput[f.Count](wait_id=WaitId("pick"), request_id="late",
                                          expected_revision=3, payload=f.Count(value=2)))
