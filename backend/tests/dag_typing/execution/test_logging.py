"""A2.5: diagnostic facts, typed control fields and the existing log facade."""

import asyncio
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
import tempfile
import time
import unittest

from pydantic import ValidationError

from app.application.engine.diagnostics import dagLog
from app.application.engine.diagnostics.events import LevelDiagnostic, ReplanDiagnostic
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.taskType import TaskType
from app.core import loggingConfig
from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationRequest, CancellationSource, ExecutionDiagnostic,
    ExecutionEventCode as Code, ExecutionSeverity,
)
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from tests.dag_typing.execution import test_level as levels
from tests.dag_typing.fixtures import GraphRuleState, LeafOutput, TestNodeError, identity


class EventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.case = levels.LevelTests()
        self.case.setUp()
        self.records = []
        self.case.executor = DAGExecutor(self.case.runner, {PythonNodeExecutor: PythonNodeExecutor()}, emit=self.records.append)

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def events(self, code):
        return [event for event in self.records if event.code == code]

    async def test_success_events_have_identity_requirements_actual_reads_and_saved_ids(self):
        self.case.node(levels.LevelRoot)
        self.case.node(levels.LevelTail, deps=("root",), reads=(levels.required("root"),))
        self.case.setup_plan()
        self.assertEqual(await self.case.execute(), LevelDecision.CONTINUE)
        self.assertEqual([event.code for event in self.records], [Code.NODE_STARTED, Code.NODE_FINISHED, Code.LEVEL_FINISHED] * 2)
        started = self.events(Code.NODE_STARTED)[1]
        finished = self.events(Code.NODE_FINISHED)[1]
        self.assertEqual(len(started.requirements), 1)
        self.assertEqual(started.reads, ())
        self.assertTrue(started.requirements[0][3])
        self.assertEqual(started.requirements[0][1], self.case.contracts[levels.LevelRoot.id].contract_id)
        self.assertEqual(finished.reads[0].result, self.events(Code.NODE_FINISHED)[0].identity)
        self.assertEqual(finished.saved_outputs, (finished.identity,))
        self.assertEqual(finished.sibling_statuses, ((levels.LevelTail.id, NodeStatus.SUCCESS),))
        self.assertLessEqual(finished.started_at, finished.completed_at)
        self.assertLessEqual(finished.completed_at, finished.timestamp)
        self.assertEqual(finished.active_plan_revision, PlanRevision("plan-1"))
        self.assertEqual(self.events(Code.LEVEL_FINISHED)[1].causes[0].identity, finished.identity)

    async def test_declared_but_unread_requirement_does_not_become_actual_read(self):
        self.case.node(levels.LevelRoot)
        node = self.case.node(levels.LevelTail, deps=("root",), reads=(levels.required("root"),))
        self.case.bindings.nodes[node.id] = replace(node, requests=())
        self.case.setup_plan()
        await self.case.execute()
        finished = self.events(Code.NODE_FINISHED)[1]
        self.assertEqual(len(finished.requirements), 1)
        self.assertEqual(finished.reads, ())

    async def test_optional_absence_from_filtered_producer_keeps_declared_contract_metadata(self):
        self.case.node(levels.LevelRoot)
        request = levels.OptionalOutput(levels.OutputRef(levels.LevelRoot.id, LeafOutput))
        self.case.node(levels.LevelTail, deps=("root",), reads=(request,))
        compiler = GraphCompiler(self.case.registry, self.case.bindings, compile_rules=lambda rules: (),
                                 evaluate_rules=lambda compiled, state: compiled.node.id != levels.LevelRoot.id)
        compiler.precompile()
        self.case.plan = compiler.compile(GraphRuleState())
        self.case.state = ExecutionState(ExecutionId("execution-1"), self.case.registry)
        await self.case.execute()
        event = self.events(Code.NODE_FINISHED)[0]
        self.assertFalse(event.requirements[0][3])
        self.assertEqual(event.reads[0].contract_id, self.case.contracts[levels.LevelRoot.id].contract_id)
        self.assertIsNone(event.reads[0].result)

    async def test_node_finish_is_emitted_after_catalog_and_status_commit(self):
        def record(event):
            if event.code == Code.NODE_FINISHED:
                self.assertEqual(self.case.state.statuses[event.identity.node_id], event.status)
                self.assertIn(event.identity, self.case.state.catalog.current_outputs)
            self.records.append(event)
        self.case.executor = DAGExecutor(self.case.runner, {PythonNodeExecutor: PythonNodeExecutor()}, emit=record)
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()

    async def test_repeated_parent_cancel_has_one_request_and_preserves_known_metadata(self):
        entered, cleaning, release, peer_done = [self.case.event() for _ in range(4)]
        async def blocked(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        async def peer(input):
            peer_done.set()
            return LeafOutput(value=1)
        self.case.node(levels.LevelRoot)
        self.case.node(levels.LevelLeft, deps=("root",), reads=(levels.required("root"),), job=blocked)
        self.case.node(levels.LevelRight, deps=("root",), job=peer)
        self.case.setup_plan()
        request = CancellationRequest(source=CancellationSource.USER, reason=CancellationReason.REQUESTED,
                                      message="stop requested", requested_at=time.time())
        task = asyncio.create_task(self.case.execute(cancellation=request))
        await self.case.reached(entered)
        await self.case.reached(peer_done)
        await asyncio.sleep(0)
        task.cancel()
        await self.case.reached(cleaning)
        self.assertEqual(len(self.events(Code.CANCEL_REQUESTED)), 1)
        self.assertEqual(len(self.events(Code.NODE_FINISHED)), 1)  # root only, no early peer commit
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        self.assertEqual(await task, LevelDecision.CANCEL)
        self.assertEqual(len(self.events(Code.CANCEL_REQUESTED)), 1)
        self.assertEqual(len(self.events(Code.CANCEL_OBSERVED)), 1)
        summary = self.events(Code.LEVEL_FINISHED)[-1]
        self.assertEqual((summary.cancel_source, summary.cancel_reason), (request.source, request.reason))
        self.assertEqual(summary.cancel_requested_at, request.requested_at)
        self.assertEqual(summary.cancel_message, request.message)
        self.assertIsNotNone(summary.cancel_observed_at)
        self.assertEqual(summary.status, NodeStatus.CANCELLED)
        self.assertEqual(summary.severity, ExecutionSeverity.WARNING)
        self.assertEqual(len(summary.reads), 1)
        self.assertEqual(len(summary.saved_outputs), 1)
        self.assertEqual(dict(summary.sibling_statuses), {levels.LevelLeft.id: NodeStatus.CANCELLED, levels.LevelRight.id: NodeStatus.SUCCESS})
        self.assertTrue(all(event.cancel_requested_at == request.requested_at for event in summary.causes))
        self.assertEqual(summary.requirements[0][0], levels.LevelRoot.id)

    async def test_node_cancellation_uses_unknown_metadata_without_a_parent_request(self):
        async def cancel(input):
            raise asyncio.CancelledError("PRIVATE_CANCEL_ARGUMENT")
        self.case.node(levels.LevelRoot, job=cancel)
        self.case.setup_plan()
        configured = CancellationRequest(source=CancellationSource.USER, reason=CancellationReason.REQUESTED)
        await self.case.execute(cancellation=configured)
        summary = self.events(Code.LEVEL_FINISHED)[0]
        self.assertEqual((summary.cancel_source, summary.cancel_reason), (CancellationSource.UNKNOWN, CancellationReason.UNKNOWN))
        self.assertEqual(self.events(Code.CANCEL_REQUESTED), [])
        self.assertEqual(len(self.events(Code.CANCEL_OBSERVED)), 1)
        self.assertNotIn("PRIVATE_CANCEL_ARGUMENT", repr(self.records))

    async def test_zero_observed_timestamp_is_preserved(self):
        async def cancel(input):
            raise asyncio.CancelledError
        ticks = iter((0.0, 0.0, 1.0))
        self.case.runner = NodeRunner(ContractValidator(), NodeValidator(), clock=ticks.__next__)
        self.case.executor = DAGExecutor(self.case.runner, {PythonNodeExecutor: PythonNodeExecutor()}, emit=self.records.append)
        self.case.node(levels.LevelRoot, job=cancel)
        self.case.setup_plan()
        await self.case.execute()
        self.assertEqual(self.events(Code.CANCEL_OBSERVED)[0].timestamp, 0.0)
        self.assertEqual(self.events(Code.CANCEL_OBSERVED)[0].completed_at, 1.0)

    async def test_cancel_summary_retains_cleanup_failure_as_error_cause(self):
        entered = self.case.event()
        async def blocked(input):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise RuntimeError("PRIVATE_CLEANUP_DATA")
        self.case.node(levels.LevelRoot, job=blocked)
        self.case.setup_plan()
        task = asyncio.create_task(self.case.execute())
        await self.case.reached(entered)
        task.cancel()
        self.assertEqual(await task, LevelDecision.CANCEL)
        summary = self.events(Code.LEVEL_FINISHED)[0]
        self.assertEqual(summary.status, NodeStatus.CANCELLED)
        self.assertEqual(summary.severity, ExecutionSeverity.ERROR)
        self.assertEqual(summary.causes[0].status, NodeStatus.FAILED)
        self.assertIn("RuntimeError", summary.causes[0].causes[0].message)
        self.assertNotIn("PRIVATE_CLEANUP_DATA", repr(self.records))

    async def test_gate_conflict_retains_both_typed_targets_without_error_payload(self):
        async def gate(input):
            raise PythonNodeError(TestNodeError(item_id=987654321))
        self.case.node(levels.LevelLeft, job=gate, policy=levels.gate_policy)
        self.case.node(levels.LevelRight, job=gate, policy=levels.gate_policy)
        self.case.setup_plan()
        self.assertEqual(await self.case.execute(), LevelDecision.FAIL)
        events = self.events(Code.REPLAN_REQUESTED)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(isinstance(event, ReplanDiagnostic) for event in events))
        self.assertTrue(all(event.next_task_type is TaskType.SCENE_INIT for event in events))
        summary = self.events(Code.LEVEL_FINISHED)[0]
        self.assertIsInstance(summary, LevelDiagnostic)
        self.assertTrue(summary.gate_conflict)
        self.assertEqual(len(summary.gate_events), 2)
        self.assertEqual(summary.severity, ExecutionSeverity.ERROR)
        self.assertIn("TestNodeError", summary.causes[0].message)
        self.assertNotIn("987654321", repr(self.records))
        roundtrip = LevelDiagnostic.model_validate_json(summary.model_dump_json())
        self.assertEqual(roundtrip.gate_events[0].next_task_type, TaskType.SCENE_INIT)

    async def test_reuse_has_only_level_summary_and_current_plan_revision(self):
        self.case.node(levels.LevelRoot)
        self.case.setup_plan()
        await self.case.execute()
        self.records.clear()
        await self.case.executor.run_python_phase(self.case.plan, self.case.state, levels.ExecutionPhase.PRE_LLM, PlanRevision("plan-2"))
        self.assertEqual(len(self.records), 1)
        event = self.records[0]
        self.assertEqual(event.code, Code.LEVEL_FINISHED)
        self.assertEqual(event.active_plan_revision, PlanRevision("plan-2"))
        self.assertEqual(event.identity.plan_revision, PlanRevision("plan-1"))
        self.assertEqual(event.reused_outputs, self.case.state.catalog.current_outputs)

    async def test_empty_phase_emits_nothing(self):
        self.case.setup_plan()
        await self.case.execute()
        self.assertEqual(self.records, [])

    async def test_info_logging_contains_required_read_and_save_metadata(self):
        self.case.node(levels.LevelRoot)
        self.case.node(levels.LevelTail, deps=("root",), reads=(levels.required("root"),))
        self.case.setup_plan()
        self.case.executor = DAGExecutor(self.case.runner, {PythonNodeExecutor: PythonNodeExecutor()})
        with self.assertLogs("app.engine.dag", level="INFO") as captured:
            await self.case.execute()
        terminal = [record.event for record in captured.records if record.event["code"] == "node_finished"]
        self.assertEqual(len(terminal), 2)
        self.assertEqual(len(terminal[1]["requirements"]), 1)
        self.assertEqual(len(terminal[1]["reads"]), 1)
        self.assertEqual(len(terminal[1]["saved_outputs"]), 1)
        self.assertTrue(all(record.levelno >= logging.INFO for record in captured.records))


class EmitterTests(unittest.TestCase):
    def event(self, **changes):
        values = dict(identity=identity(), pass_number=0, phase=levels.ExecutionPhase.PRE_LLM, level=0,
                      timestamp=2.0, code=Code.NODE_FINISHED, severity=ExecutionSeverity.INFO,
                      status=NodeStatus.SUCCESS, message="committed")
        values.update(changes)
        return ExecutionDiagnostic(**values)

    def test_level_mapping_and_no_handler_installation(self):
        for severity, level in ((ExecutionSeverity.DEBUG, logging.DEBUG), (ExecutionSeverity.INFO, logging.INFO),
                                (ExecutionSeverity.WARNING, logging.WARNING), (ExecutionSeverity.ERROR, logging.ERROR)):
            with self.subTest(severity=severity), self.assertLogs("app.engine.dag", level="DEBUG") as captured:
                logger = logging.getLogger("app.engine.dag")
                handlers = tuple(logger.handlers)
                dagLog.emit(self.event(severity=severity))
                self.assertEqual(tuple(logger.handlers), handlers)
            self.assertEqual(len(captured.records), 1)
            self.assertEqual(captured.records[0].levelno, level)
            self.assertIsNone(captured.records[0].exc_info)

    def test_unknown_subclass_payload_is_not_serialized(self):
        class UnexpectedDiagnostic(ExecutionDiagnostic):
            output: LeafOutput
        event = UnexpectedDiagnostic(**dict(self.event()), output=LeafOutput(value=987654321))
        with self.assertLogs("app.engine.dag", level="INFO") as captured:
            dagLog.emit(event)
        wire = captured.records[0].event
        self.assertNotIn("output", wire)
        self.assertNotIn("987654321", json.dumps(wire))

    def test_typed_control_fields_survive_wire_without_subclass_payload(self):
        class UnexpectedReplan(ReplanDiagnostic):
            output: LeafOutput
        class UnexpectedLevel(LevelDiagnostic):
            output: LeafOutput
        replan = UnexpectedReplan(**dict(self.event(code=Code.REPLAN_REQUESTED, status=NodeStatus.GATED)),
                                  next_task_type=TaskType.SCENE_INIT, output=LeafOutput(value=987654321))
        regular = ReplanDiagnostic(**dict(self.event(code=Code.REPLAN_REQUESTED, status=NodeStatus.GATED)), next_task_type=TaskType.SCENE_INIT)
        level = UnexpectedLevel(**dict(self.event(code=Code.LEVEL_FINISHED, status=NodeStatus.GATED)),
                                gate_events=(regular,), output=LeafOutput(value=987654321))
        for event in (replan, level):
            with self.subTest(event=type(event)), self.assertLogs("app.engine.dag", level="INFO") as captured:
                dagLog.emit(event)
            wire = captured.records[0].event
            self.assertNotIn("output", wire)
            self.assertNotIn("987654321", json.dumps(wire))
            if event is replan:
                self.assertEqual(wire["next_task_type"], TaskType.SCENE_INIT.value)
            else:
                self.assertEqual(wire["gate_events"][0]["next_task_type"], TaskType.SCENE_INIT.value)

    def test_cancellation_request_is_frozen_strict_and_roundtrips(self):
        request = CancellationRequest(source=CancellationSource.TIMEOUT, reason=CancellationReason.DEADLINE_EXCEEDED, requested_at=1.0)
        self.assertEqual(CancellationRequest.model_validate_json(request.model_dump_json()), request)
        for changes in ({"source": "user"}, {"reason": "requested"}, {"requested_at": float("nan")}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                CancellationRequest(**changes)
        with self.assertRaises(ValidationError):
            request.message = "changed"

    def test_server_route_writes_one_structured_line_to_existing_facade(self):
        self.assertEqual(loggingConfig.route_for("app.engine.dag"), ("engine", "dagExecution"))
        self.assertEqual(loggingConfig.route_for("app.engine.dag.child"), ("engine", "dagExecution"))
        self.assertIsNone(loggingConfig.route_for("app.engine.dagOther"))
        root = logging.getLogger()
        old_level = root.level
        loggingConfig._remove_facade_handlers()
        try:
            with tempfile.TemporaryDirectory() as directory:
                try:
                    loggingConfig.setup_logging(level=logging.INFO, profile="server", logs_dir=directory, stream=io.StringIO())
                    dagLog.emit(self.event())
                    loggingConfig.flush_console_queue()
                    for handler in root.handlers:
                        handler.flush()
                    path = Path(directory) / "engine" / "dagExecution.log"
                    lines = path.read_text(encoding="utf-8").splitlines()
                    self.assertEqual(len(lines), 1)
                    wire = json.loads(lines[0])
                    self.assertEqual(wire["logger"], "app.engine.dag")
                    self.assertEqual(wire["event"]["identity"]["execution_id"], self.event().identity.execution_id)
                    self.assertEqual(wire["event"]["code"], "node_finished")
                    self.assertFalse((Path(directory) / "core" / "runtime.log").exists())
                finally:
                    loggingConfig._remove_facade_handlers()
        finally:
            loggingConfig._remove_facade_handlers()
            root.setLevel(old_level)
