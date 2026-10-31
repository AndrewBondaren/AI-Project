"""A3.5: one conversation, validation/repair and atomic group publication."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
import gc
import json
from time import time
import unittest
from unittest.mock import patch
import weakref

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OutputRef, RequiredOutput
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionPlan import LLMGroup
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.engine.runtime.repair.repairOrchestrator import RepairOrchestrator
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.llmValidator import LLMValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.nodeValidationError import NodeErrorSeverity, NodeValidationError
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.diagnostics import ExecutionEventCode
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from tests.dag_typing.fixtures import CompositeOutput, GraphBindings, GraphRuleState, LeafOutput, NodeInput, TestNodeError
from tests.dag_typing.llm.test_payload import Registry


@dataclass(frozen=True, kw_only=True)
class GroupNode(LLMNode[NodeInput, LeafOutput, TestNodeError]):
    dsl: str = "node"
    prepare: Callable[[DAGReadView], Awaitable[NodeInput]] | None = None
    calls: list[str] = field(default_factory=list, compare=False)

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        self.calls.append("prepare")
        return await self.prepare(view) if self.prepare else NodeInput(value=1)


class First(GroupNode):
    id = NodeId("first")


class Second(GroupNode):
    id = NodeId("second")


class Request:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.conversations = []

    async def __call__(self, messages, schema, *, enable_thinking, temperature):
        self.conversations.append(messages)
        self.calls.append((id(messages), [(m.role, m.content) for m in messages], schema, enable_thinking, temperature))
        if not self.responses:
            raise AssertionError("unexpected extra LLM request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return await response() if callable(response) else response


def response(**sections):
    return json.dumps({node: {"value": value} for node, value in sections.items()})


class GroupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry, self.bindings = NodeRegistry(), GraphBindings()
        self.contracts, self.nodes, self.events = {}, {}, []
        self.options = LLMExecutionOptions(player_message="hello", language="ru", repair_iterations=2, repair_mode=RepairMode.MAXIMUM)
        self.dsl = DSLResolver(Registry())
        validator = LLMValidator(ContractValidator(), NodeValidator())
        self.aggregate = LLMAggregateExecutor(LLMGroupPayloadBuilder(self.dsl), validator,
                                             DSLFailureProjector(self.dsl), RepairOrchestrator(RepairBuilder(self.dsl)))
        self.coordinator = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {}, emit=self.events.append)

    def node(self, cls, *, reads=(), validator=None, **kwargs):
        contract = NodeContract[NodeInput, LeafOutput, TestNodeError](
            NodeInput, LeafOutput, ContractId("test." + cls.id), ContractVersion("1"), reads,
            error_types=(TestNodeError,), validator=validator,
        )
        node = cls(id=cls.id, **kwargs)
        self.registry.register_llm(cls, contract)
        self.contracts[cls.id] = contract
        self.nodes[cls.id] = node
        self.bindings.nodes[cls.id] = node
        return node

    def setup_plan(self):
        compiler = GraphCompiler(self.registry, self.bindings, compile_rules=lambda rules: (), evaluate_rules=lambda node, state: True)
        compiler.precompile()
        self.plan = compiler.compile(GraphRuleState())
        self.state = ExecutionState(ExecutionId("llm-execution"), self.registry)

    async def run_group(self, request, **kwargs):
        return await self.coordinator.run_llm_phase(self.plan, self.state, PlanRevision("plan-1"), self.aggregate,
                                                   request, options=self.options, **kwargs)

    def current(self):
        return {identity.node_id for identity in self.state.catalog.current_outputs}

    def two_nodes(self, **kwargs):
        self.node(First, **kwargs)
        self.node(Second)
        self.setup_plan()

    async def test_initial_request_covers_entire_group_and_publishes_typed_outputs_once(self):
        self.two_nodes(enable_thinking=True)
        request = Request([response(first=1, second=2)])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(set(request.calls[0][2]["properties"]), {First.id, Second.id})
        self.assertTrue(request.calls[0][3])
        self.assertEqual(self.current(), {First.id, Second.id})
        record = self.state.catalog.capture().record(First.id, self.contracts[First.id])
        self.assertIsInstance(record.output, LeafOutput)
        self.assertEqual(record.identity.attempt, 1)
        self.assertTrue(self.state.catalog.is_quiescent)
        self.assertFalse(self.state.is_active)
        self.assertEqual(len(self.events), 5)  # two started, two finished, one group summary

    async def test_order_only_levels_still_use_one_request(self):
        self.node(First)
        self.node(Second, deps=(First.id,))
        self.setup_plan()
        self.assertEqual(len(self.plan.llm_groups[0].levels), 2)
        request = Request([response(first=1, second=2)])
        await self.run_group(request)
        self.assertEqual(len(request.calls), 1)

    async def test_repair_uses_same_conversation_failed_schema_and_revalidates_successes(self):
        seen = []
        def validator(ctx):
            seen.append((ctx.identity.node_id, ctx.repair_attempt))
            return ValidationResult(status=ValidationStatus.OK)
        self.node(First, validator=validator)
        self.node(Second, validator=validator)
        self.setup_plan()
        async def repair():
            self.assertEqual(self.current(), set())
            return response(second=2)
        request = Request([response(first=1, second="bad"), repair])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual([call[0] for call in request.calls], [request.calls[0][0]] * 2)
        self.assertEqual([role for role, _ in request.calls[1][1]], ["user", "assistant", "user"])
        self.assertEqual(set(request.calls[1][2]["properties"]), {Second.id})
        self.assertEqual(seen, [(First.id, 0), (First.id, 1), (Second.id, 1)])
        self.assertEqual(self.current(), {First.id, Second.id})

    async def test_system_role_is_present_once_in_same_conversation(self):
        self.two_nodes()
        self.options = replace(self.options, system_role=True)
        request = Request([response(first=1), response(second=2)])
        await self.run_group(request)
        roles = [role for role, _ in request.calls[1][1]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertNotIn("dsl", json.loads(request.calls[1][1][-1][1]))

    async def test_malformed_envelope_and_missing_sections_can_be_repaired(self):
        self.two_nodes()
        request = Request(["{broken", response(first=1), response(second=2)])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual(len(request.calls), 3)
        self.assertEqual(set(request.calls[2][2]["properties"]), {Second.id})

    async def test_repair_limit_discards_successful_sibling_and_closes_all_attempts(self):
        self.two_nodes()
        request = Request([response(first=1, second="bad")] + [response(second="bad")] * 2)
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(len(request.calls), 3)
        self.assertEqual(self.current(), set())
        self.assertEqual(set(self.state.statuses.values()), {NodeStatus.FAILED})
        self.assertEqual(len(self.state.catalog.closed_attempts), 2)
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_zero_repair_limit_never_sends_extra_request(self):
        self.two_nodes()
        self.options = replace(self.options, repair_iterations=0)
        request = Request([response(first=1)])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.current(), set())

    async def test_fatal_semantic_status_stops_without_repair(self):
        for status in (ValidationStatus.FAIL, ValidationStatus.USER_ERROR):
            with self.subTest(status=status):
                self.setUp()
                self.node(First, validator=lambda ctx: ValidationResult(status=status))
                self.node(Second)
                self.setup_plan()
                request = Request([response(first=1, second=2)])
                self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
                self.assertEqual(len(request.calls), 1)
                self.assertEqual(self.current(), set())

    async def test_previously_successful_section_is_semantically_checked_after_repair(self):
        def validator(ctx):
            return ValidationResult(status=ValidationStatus.FAIL if ctx.repair_attempt else ValidationStatus.OK)
        self.node(First, validator=validator)
        self.node(Second)
        self.setup_plan()
        request = Request([response(first=1), response(second=2)])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(self.current(), set())

    async def test_current_group_reuses_after_snapshot_restore_without_client_call(self):
        self.two_nodes()
        await self.run_group(Request([response(first=1, second=2)]))
        snapshot = ExecutionSnapshotService().capture(self.state)
        self.state = await ExecutionSnapshotService().restore(snapshot, self.registry)
        request = Request([])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual(request.calls, [])
        self.assertEqual(self.nodes[First.id].calls, ["prepare"])
        self.assertEqual(len(self.state.levels[-1].reused_outputs), 2)

    async def test_partially_invalidated_group_reruns_all_members(self):
        self.two_nodes()
        await self.run_group(Request([response(first=1, second=2)]))
        identity = self.state.catalog.begin_attempt(First.id, PlanRevision("other"))
        self.state.catalog.close_attempt(identity)
        request = Request([response(first=3, second=4)])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.nodes[Second.id].calls, ["prepare", "prepare"])
        self.assertEqual(dict(self.state.catalog.attempt_counters), {First.id: 3, Second.id: 2})

    async def test_new_pass_and_explicit_rerun_each_rerun_entire_group(self):
        self.two_nodes()
        request = Request([response(first=1, second=2)] * 3)
        await self.run_group(request)
        await self.run_group(request, pass_number=1)
        await self.run_group(request, pass_number=1, rerun=(First.id,))
        self.assertEqual(len(request.calls), 3)
        self.assertEqual(dict(self.state.catalog.attempt_counters), {First.id: 3, Second.id: 3})

    async def test_domain_freshness_confirmation_controls_group_reuse(self):
        async def prepare(view):
            view.record_domain_read("world", DomainRevision("r1"))
            return NodeInput(value=1)
        self.two_nodes(prepare=prepare)
        request = Request([response(first=1, second=2)] * 2)
        await self.run_group(request)
        await self.run_group(request, confirmed_domain_revisions={"world": DomainRevision("r1")})
        self.assertEqual(len(request.calls), 1)
        await self.run_group(request)
        self.assertEqual(len(request.calls), 2)

    async def test_two_temperature_groups_allow_reads_from_completed_group(self):
        required = RequiredOutput(OutputRef(First.id, LeafOutput))
        async def prepare(view):
            return NodeInput(value=view.require(required).value)
        self.node(First)
        self.node(Second, temperature=1.0, deps=(First.id,), reads=(required,), prepare=prepare)
        self.setup_plan()
        request = Request([response(first=4), response(second=5)])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        self.assertEqual(len(request.calls), 2)
        self.assertNotEqual(request.calls[0][0], request.calls[1][0])
        self.assertEqual([call[4] for call in request.calls], [0.0, 1.0])
        wire = json.loads(request.calls[1][1][0][1])
        self.assertEqual(wire[Second.id]["context_data"], {"value": 4})
        saved = self.state.catalog.capture().record(Second.id, self.contracts[Second.id])
        self.assertEqual(saved.reads[0].result.node_id, First.id)

    async def test_sibling_read_contract_is_rejected_before_any_client_call(self):
        required = RequiredOutput(OutputRef(First.id, LeafOutput))
        self.node(First)
        self.node(Second, deps=(First.id,), reads=(required,))
        with self.assertRaisesRegex(ValueError, "same LLM group"):
            self.setup_plan()

    async def test_prepare_error_admits_declared_error_and_never_calls_client(self):
        error = TestNodeError(item_id=1)
        async def prepare(view):
            raise PythonNodeError(error)
        self.two_nodes(prepare=prepare)
        request = Request([])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(request.calls, [])
        self.assertIs(self.state.catalog.node_error(First.id, self.contracts[First.id]), error)
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_request_and_validator_exceptions_discard_group(self):
        for fail_validator in (False, True):
            with self.subTest(fail_validator=fail_validator):
                self.setUp()
                def validator(ctx):
                    raise RuntimeError("private validator error")
                self.two_nodes(validator=validator if fail_validator else None)
                request = Request([response(first=1, second=2) if fail_validator else RuntimeError("private transport error")])
                self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
                self.assertEqual(self.current(), set())
                self.assertNotIn("private", str(self.events))

    async def test_cancellation_waits_for_cleanup_and_repeated_cancel_does_not_interrupt_it(self):
        self.two_nodes()
        entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def blocked():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        request = Request([blocked])
        task = asyncio.create_task(self.run_group(request))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        await asyncio.wait_for(cleaning.wait(), 3)
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.assertEqual(self.current(), set())
        release.set()
        self.assertEqual(await asyncio.wait_for(task, 3), LevelDecision.CANCEL)
        self.assertTrue(self.state.catalog.is_quiescent)
        self.assertEqual(sum(event.code == ExecutionEventCode.CANCEL_REQUESTED for event in self.events), 1)
        snapshot = ExecutionSnapshotService().capture(self.state)
        self.state = await ExecutionSnapshotService().restore(snapshot, self.registry)
        self.assertEqual(await self.run_group(Request([response(first=3, second=4)])), LevelDecision.CONTINUE)

    async def test_provider_suppressed_cancellation_cannot_publish_success(self):
        self.two_nodes()
        entered = asyncio.Event()
        async def suppress():
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return response(first=1, second=2)
        task = asyncio.create_task(self.run_group(Request([suppress])))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        self.assertEqual(await asyncio.wait_for(task, 3), LevelDecision.CANCEL)
        self.assertEqual(self.current(), set())

    async def test_cancel_during_repair_does_not_publish_initial_success(self):
        self.two_nodes()
        request = Request([response(first=1), asyncio.CancelledError()])
        self.assertEqual(await self.run_group(request), LevelDecision.CANCEL)
        self.assertEqual(self.current(), set())

    async def test_batch_admission_failure_is_atomic_even_if_last_record_is_wrong(self):
        self.two_nodes()
        original = DAGContext.publish_batch
        def corrupt(catalog, records):
            last = records[-1].model_copy(update={"contract_version": ContractVersion("wrong")})
            return original(catalog, (*records[:-1], last))
        with patch.object(DAGContext, "publish_batch", corrupt):
            self.assertEqual(await self.run_group(Request([response(first=1, second=2)])), LevelDecision.FAIL)
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)
        self.assertEqual(len(self.state.catalog.closed_attempts), 2)

    async def test_stale_external_read_cannot_partially_publish_group(self):
        required = RequiredOutput(OutputRef(First.id, LeafOutput))
        async def prepare(view):
            return NodeInput(value=view.require(required).value)
        self.node(First)
        self.node(Second, temperature=1, deps=(First.id,), reads=(required,), prepare=prepare)
        self.setup_plan()
        async def stale():
            identity = self.state.catalog.begin_attempt(First.id, PlanRevision("changed"))
            self.state.catalog.close_attempt(identity)
            return response(second=2)
        self.assertEqual(await self.run_group(Request([response(first=1), stale])), LevelDecision.FAIL)
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_successful_output_identity_survives_commit_and_trace_does_not_retain_payload(self):
        references = []
        def validator(ctx):
            references.append(weakref.ref(ctx.output))
            return ValidationResult(status=ValidationStatus.OK)
        self.two_nodes(validator=validator)
        with patch.object(LeafOutput, "model_validate", side_effect=AssertionError("schema rerun at commit")):
            self.assertEqual(await self.run_group(Request([response(first=1, second=2)])), LevelDecision.CONTINUE)
        self.assertIs(self.state.catalog.capture().record(First.id, self.contracts[First.id]).output, references[0]())
        traces = self.state.traces
        self.state.release()
        await asyncio.sleep(0)
        gc.collect()
        self.assertTrue(traces)
        self.assertIsNone(references[0]())

    async def test_invalid_group_preflight_does_not_open_attempts(self):
        self.two_nodes()
        self.plan = replace(self.plan, llm_groups=(LLMGroup(9.0, ((First.id, Second.id),)),))
        request = Request([])
        with self.assertRaises(TypeError):
            await self.run_group(request)
        self.assertEqual(request.calls, [])
        self.assertEqual(self.state.catalog.attempt_counters, ())

    async def test_heterogeneous_output_schemas_publish_owning_pojo_instances(self):
        class CompositeNode(LLMNode[NodeInput, CompositeOutput, TestNodeError]):
            id = NodeId("composite")
            async def prepare_input(self, view):
                return NodeInput(value=1)
        self.node(First)
        contract = NodeContract[NodeInput, CompositeOutput, TestNodeError](
            NodeInput, CompositeOutput, ContractId("test.composite"), ContractVersion("1"), (), error_types=(TestNodeError,),
        )
        self.registry.register_llm(CompositeNode, contract)
        self.bindings.nodes[CompositeNode.id] = CompositeNode(id=CompositeNode.id, dsl="node")
        self.setup_plan()
        request = Request([json.dumps({First.id: {"value": 1}, CompositeNode.id: {"leaves": [{"value": 2}]}})])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        record = self.state.catalog.capture().record(CompositeNode.id, contract)
        self.assertIsInstance(record.output, CompositeOutput)
        self.assertEqual(record.output.leaves[0].value, 2)

    async def test_economy_repair_sends_minimal_wire_in_initial_conversation(self):
        self.two_nodes()
        self.options = replace(self.options, repair_mode=RepairMode.ECONOMY)
        request = Request([response(first=1), response(second=2)])
        self.assertEqual(await self.run_group(request), LevelDecision.CONTINUE)
        wire = json.loads(request.calls[1][1][-1][1])
        self.assertEqual(set(wire), {"type", "errors"})
        self.assertEqual(request.calls[0][0], request.calls[1][0])
        self.assertEqual(set(request.calls[1][2]["properties"]), {Second.id})

    async def test_cleanup_failure_keeps_cancel_decision_and_failed_metadata(self):
        self.two_nodes()
        entered = asyncio.Event()
        async def cleanup_fail():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise RuntimeError("private cleanup failure")
        task = asyncio.create_task(self.run_group(Request([cleanup_fail])))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        self.assertEqual(await asyncio.wait_for(task, 3), LevelDecision.CANCEL)
        self.assertEqual(self.current(), set())
        self.assertEqual(set(self.state.statuses.values()), {NodeStatus.FAILED})
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_repeated_cancel_racing_completed_cleanup_keeps_failure_metadata(self):
        self.two_nodes()
        entered = asyncio.Event()
        async def cleanup_fail():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                task.cancel()  # second parent cancel as the aggregate completes
                raise RuntimeError("cleanup failure")
        task = asyncio.create_task(self.run_group(Request([cleanup_fail])))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        self.assertEqual(await asyncio.wait_for(task, 3), LevelDecision.CANCEL)
        self.assertEqual(set(self.state.statuses.values()), {NodeStatus.FAILED})
        self.assertEqual(self.current(), set())

    async def test_invalid_prepared_input_fails_before_initial_call(self):
        async def prepare(view):
            return {"value": 1}
        self.two_nodes(prepare=prepare)
        request = Request([])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(request.calls, [])
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_foreign_local_outcome_identity_discards_entire_group(self):
        self.two_nodes()
        execute = self.aggregate.execute
        async def foreign(*args, **kwargs):
            outcomes = await execute(*args, **kwargs)
            first = outcomes[0]
            identity = first.identity.model_copy(update={"execution_id": ExecutionId("foreign")})
            return (replace(first, identity=identity), *outcomes[1:])
        with patch.object(self.aggregate, "execute", side_effect=foreign):
            self.assertEqual(await self.run_group(Request([response(first=1, second=2)])), LevelDecision.FAIL)
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_failed_group_stops_later_temperature_groups(self):
        self.node(First)
        self.node(Second, temperature=1.0)
        self.setup_plan()
        self.options = replace(self.options, repair_iterations=0)
        request = Request(["{}"])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(len(request.calls), 1)
        self.assertEqual(self.nodes[Second.id].calls, [])
        self.assertEqual(dict(self.state.catalog.attempt_counters), {First.id: 1})

    async def test_synchronous_semantic_self_cancel_cannot_publish_outputs(self):
        def validator(ctx):
            asyncio.current_task().cancel()
            return ValidationResult(status=ValidationStatus.OK)
        self.two_nodes(validator=validator)
        self.assertEqual(await self.run_group(Request([response(first=1, second=2)])), LevelDecision.CANCEL)
        self.assertEqual(self.current(), set())
        self.assertTrue(self.state.catalog.is_quiescent)

    async def test_repair_cannot_overwrite_a_section_outside_failed_subset(self):
        self.two_nodes()
        self.options = replace(self.options, repair_iterations=1)
        request = Request([response(first=1), response(first=9, second=2)])
        self.assertEqual(await self.run_group(request), LevelDecision.FAIL)
        self.assertEqual(len(request.calls), 2)
        self.assertEqual(self.current(), set())

    async def test_preceding_phase_stop_prevents_llm_start(self):
        self.two_nodes()
        for decision in (LevelDecision.CANCEL, LevelDecision.FAIL, LevelDecision.REPLAN):
            self.state.finish_level(ExecutionLevelSnapshot(ExecutionPhase.PRE_LLM, 0, 0, decision, (), (), (), None, time()))
            request = Request([])
            self.assertEqual(await self.run_group(request), decision)
            self.assertEqual(request.calls, [])
            self.assertEqual(self.state.catalog.attempt_counters, ())
