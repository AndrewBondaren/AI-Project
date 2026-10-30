"""A1.3: graph contracts, conditional selection and aggregate LLM ordering."""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.nodeTypes.support.nodeCost import NodeCost
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.rules.rule import Rule
from app.application.engine.rules.ruleCompiler import RuleCompiler
from app.application.engine.rules.ruleEngine import RuleEngine
from app.application.engine.rules.ruleHandlerRegistry import RuleHandlerRegistry
from app.application.engine.rules.taskRuleHandler import TaskRuleHandler
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId
from tests.dag_typing.fixtures import (
    CompositeOutput, DerivedLeafOutput, FakeExecutor, FakeReadView, GraphBindings, GraphConsumer,
    GraphDerivedProducer, GraphLLMConsumer, GraphLLMProducer, GraphPeer,
    GraphOptionalConsumer, GraphProducer, GraphRuleState, LeafOutput, NodeInput,
    LEAF_CONTRACT, OPTIONAL_LEAF, REQUIRED_LEAF, TypedPythonNode,
)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.registry = NodeRegistry()
        self.bindings = GraphBindings()
        handlers = RuleHandlerRegistry()
        handlers.register("task", TaskRuleHandler())
        self.compiler = GraphCompiler(
            self.registry, self.bindings, compile_rules=RuleCompiler(handlers).compile,
            evaluate_rules=RuleEngine().evaluate,
        )

    def python(self, cls=GraphProducer, *, deps=(), reads=(), phase=ExecutionPhase.PRE_LLM,
               priority=50, cpu=1.0, tasks=(TaskType.SCENE_NARRATION,), output_type=LeafOutput):
        contract = NodeContract(NodeInput, output_type, ContractId(cls.id), ContractVersion("1"), reads)
        self.registry.register_python(cls, FakeExecutor, contract)
        self.bindings.nodes[cls.id] = cls(
            id=cls.id, deps=tuple(NodeId(dep) for dep in deps), phase=phase,
            priority=priority, cost=NodeCost(cpu=cpu), supported_tasks=tasks,
            rules=(Rule(type="task", params={}),),
        )
        return contract

    def llm(self, cls=GraphLLMProducer, *, deps=(), reads=(), temperature=0.0,
            tasks=(TaskType.SCENE_NARRATION,)):
        contract = NodeContract(NodeInput, LeafOutput, ContractId(cls.id), ContractVersion("1"), reads)
        self.registry.register_llm(cls, contract)
        self.bindings.nodes[cls.id] = cls(
            id=cls.id, deps=tuple(NodeId(dep) for dep in deps), temperature=temperature,
            supported_tasks=tasks, rules=(Rule(type="task", params={}),),
        )
        return contract

    def read(self, producer="producer", *, output_type=LeafOutput, optional=False):
        ref = OutputRef(NodeId(producer), output_type)
        return OptionalOutput(ref) if optional else RequiredOutput(ref)

    def plan(self, state=None):
        self.compiler.precompile()
        return self.compiler.compile(state or GraphRuleState())

    def test_compile_requires_successful_precompile(self):
        with self.assertRaisesRegex(RuntimeError, "precompile"):
            self.compiler.compile(GraphRuleState())

    def test_empty_graph_has_empty_phases_and_zero_cost(self):
        plan = self.plan()
        self.assertEqual((plan.pre_llm_levels, plan.llm_groups, plan.post_llm_levels), ((), (), ()))
        self.assertEqual(dict(plan.nodes), {})
        self.assertEqual(plan.estimated_cost, 0)

    def test_chain_and_diamond_use_deps_and_keep_parallel_siblings(self):
        self.python(GraphProducer)
        self.python(GraphConsumer, deps=("producer",), reads=(self.read(),))
        self.python(GraphPeer, deps=("producer",), reads=(self.read(optional=True),))
        self.llm(deps=("consumer", "peer"))
        plan = self.plan()
        self.assertEqual(plan.pre_llm_levels, (("producer",), ("consumer", "peer")))
        self.assertEqual(plan.llm_groups[0].levels, (("llm-producer",),))

    def test_levels_use_priority_then_node_id_independent_of_registration_order(self):
        self.python(GraphPeer, priority=50)
        self.python(GraphConsumer, priority=80)
        self.python(GraphProducer, priority=50)
        self.assertEqual(self.plan().pre_llm_levels, (("consumer", "peer", "producer"),))

    def test_order_only_dependency_does_not_require_a_read(self):
        self.python()
        contract = self.python(GraphConsumer, deps=("producer",))
        plan = self.plan()
        self.assertEqual(plan.pre_llm_levels, (("producer",), ("consumer",)))
        self.assertEqual(plan.registrations[NodeId("consumer")].contract.reads, ())
        self.assertIs(plan.get(NodeId("consumer"), contract).node, self.bindings.nodes[NodeId("consumer")])

    def test_unknown_required_and_optional_producers_are_rejected(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                self.setUp()
                self.python(GraphConsumer, reads=(self.read("missing", optional=optional),))
                with self.assertRaisesRegex(ValueError, "unknown producer 'missing'"):
                    self.compiler.precompile()

    def test_unknown_order_only_dependency_is_rejected(self):
        self.python(GraphConsumer, deps=("missing",))
        with self.assertRaisesRegex(ValueError, "unknown dependency 'missing'"):
            self.compiler.precompile()

    def test_read_requires_explicit_deps_edge(self):
        self.python()
        self.python(GraphConsumer, reads=(self.read(),))
        with self.assertRaisesRegex(ValueError, "producer.*missing from deps"):
            self.compiler.precompile()

    def test_required_and_optional_output_mismatches_are_errors(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                self.setUp()
                self.python()
                self.python(GraphConsumer, deps=("producer",), reads=(self.read(output_type=CompositeOutput, optional=optional),))
                with self.assertRaisesRegex(TypeError, "incompatible Output LeafOutput; expected CompositeOutput"):
                    self.compiler.precompile()

    def test_output_subclass_is_compatible_with_declared_base_contract(self):
        self.python(GraphDerivedProducer, output_type=DerivedLeafOutput)
        self.python(GraphConsumer, deps=("derived-producer",), reads=(self.read("derived-producer"),))
        self.assertEqual(self.plan().pre_llm_levels, (("derived-producer",), ("consumer",)))

    def test_cycle_and_self_dependency_are_rejected(self):
        self.python(deps=("consumer",))
        self.python(GraphConsumer, deps=("producer",))
        with self.assertRaisesRegex(ValueError, "cycle detected"):
            self.compiler.precompile()
        self.setUp()
        self.python(deps=("producer",))
        with self.assertRaisesRegex(ValueError, "cycle detected"):
            self.compiler.precompile()

    def test_duplicate_deps_are_rejected(self):
        self.python()
        self.python(GraphConsumer, deps=("producer", "producer"))
        with self.assertRaisesRegex(ValueError, "duplicate deps"):
            self.compiler.precompile()

    def test_backwards_phase_edges_are_rejected(self):
        for scenario in ("pre-post", "pre-llm", "llm-post"):
            with self.subTest(scenario=scenario):
                self.setUp()
                if scenario == "pre-post":
                    self.python(phase=ExecutionPhase.POST_LLM)
                    self.python(GraphConsumer, deps=("producer",))
                elif scenario == "pre-llm":
                    self.llm()
                    self.python(GraphConsumer, deps=("llm-producer",))
                else:
                    self.python(phase=ExecutionPhase.POST_LLM)
                    self.llm(deps=("producer",))
                with self.assertRaisesRegex(ValueError, "later phase/group producer"):
                    self.compiler.precompile()

    def test_forward_phase_reads_and_post_levels_are_preserved(self):
        self.python()
        self.llm(deps=("producer",), reads=(self.read(),))
        self.python(GraphConsumer, phase=ExecutionPhase.POST_LLM,
                    deps=("llm-producer",), reads=(self.read("llm-producer"),))
        self.python(GraphPeer, phase=ExecutionPhase.POST_LLM, deps=("consumer",))
        plan = self.plan()
        self.assertEqual(plan.pre_llm_levels, (("producer",),))
        self.assertEqual(plan.post_llm_levels, (("consumer",), ("peer",)))

    def test_same_llm_group_read_is_rejected_even_with_ordering_levels(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                self.setUp()
                self.llm()
                self.llm(GraphLLMConsumer, deps=("llm-producer",),
                         reads=(self.read("llm-producer", optional=optional),))
                with self.assertRaisesRegex(ValueError, "same LLM group"):
                    self.compiler.precompile()

    def test_same_llm_group_order_only_edge_stays_in_one_aggregate(self):
        self.llm()
        self.llm(GraphLLMConsumer, deps=("llm-producer",))
        groups = self.plan().llm_groups
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].levels, (("llm-producer",), ("llm-consumer",)))

    def test_llm_groups_are_sorted_and_prior_group_output_can_be_read(self):
        self.llm(GraphLLMConsumer, temperature=0.8, deps=("llm-producer",), reads=(self.read("llm-producer"),))
        self.llm(temperature=0.1)
        groups = self.plan().llm_groups
        self.assertEqual([group.temperature for group in groups], [0.1, 0.8])
        self.assertEqual([group.levels for group in groups], [(("llm-producer",),), (("llm-consumer",),)])

    def test_dependency_on_later_temperature_group_is_rejected(self):
        self.llm(temperature=0.8)
        self.llm(GraphLLMConsumer, temperature=0.1, deps=("llm-producer",))
        with self.assertRaisesRegex(ValueError, "later phase/group producer"):
            self.compiler.precompile()

    def test_nonfinite_temperature_is_rejected(self):
        for temperature in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(temperature=temperature):
                self.setUp()
                self.llm(temperature=temperature)
                with self.assertRaisesRegex(ValueError, "non-finite"):
                    self.compiler.precompile()

    def test_excluded_producer_has_no_fake_result_and_consumer_keeps_read(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                self.setUp()
                self.python(tasks=(TaskType.SCENE_COMBAT,))
                read = self.read(optional=optional)
                contract = self.python(GraphConsumer, deps=("producer",), reads=(read,))
                plan = self.plan()
                self.assertEqual(plan.pre_llm_levels, (("consumer",),))
                self.assertNotIn("producer", plan.nodes)
                self.assertIs(plan.registrations[NodeId("consumer")].contract, contract)
                self.assertIs(contract.reads[0], read)
                # Runtime presence checks belong to A2.1/A2.3, not compilation.

    def test_rule_filter_does_not_hide_invalid_declared_graph(self):
        self.python(GraphConsumer, deps=("missing",), tasks=(TaskType.SCENE_COMBAT,))
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            self.compiler.precompile()

    def test_filter_and_cost_follow_pass_state_without_recreating_nodes(self):
        self.python(cpu=2.5)
        self.python(GraphConsumer, cpu=7.0, tasks=(TaskType.SCENE_COMBAT,))
        self.compiler.precompile()
        first = self.compiler.compile(GraphRuleState())
        second = self.compiler.compile(GraphRuleState(task_type=TaskType.SCENE_COMBAT))
        self.assertEqual(set(first.nodes), {"producer"})
        self.assertEqual(set(second.nodes), {"consumer"})
        self.assertEqual((first.estimated_cost, second.estimated_cost), (2.5, 7.0))

    def test_factory_result_must_match_registered_class_and_id(self):
        self.python()
        self.bindings.nodes[NodeId("producer")] = object()
        with self.assertRaisesRegex(TypeError, "outside binding"):
            self.compiler.precompile()
        with self.assertRaisesRegex(RuntimeError, "precompile"):
            self.compiler.compile(GraphRuleState())

    def test_registry_changes_require_recompile(self):
        self.python()
        self.compiler.precompile()
        self.python(GraphConsumer)
        with self.assertRaisesRegex(RuntimeError, "registry changed"):
            self.compiler.compile(GraphRuleState())
        self.compiler.precompile()
        self.assertEqual(len(self.compiler.compile(GraphRuleState()).nodes), 2)

    def test_plan_maps_and_groups_are_immutable_and_get_is_contract_checked(self):
        contract = self.python()
        self.llm()
        plan = self.plan()
        self.assertIs(plan.get(NodeId("producer"), contract).node, self.bindings.nodes[NodeId("producer")])
        with self.assertRaises(TypeError):
            plan.nodes[NodeId("missing")] = plan.nodes[NodeId("producer")]
        with self.assertRaises(TypeError):
            plan.registrations[NodeId("missing")] = plan.registrations[NodeId("producer")]
        with self.assertRaises(FrozenInstanceError):
            plan.llm_groups[0].temperature = 0.5
        wrong = NodeContract(NodeInput, CompositeOutput, contract.contract_id, contract.version, ())
        with self.assertRaisesRegex(TypeError, "contract does not match plan"):
            plan.get(NodeId("producer"), wrong)

    def test_target_compiler_import_does_not_load_production_nodes(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run(
            [sys.executable, "-c", "import sys, json; from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler; print(json.dumps([key for key in sys.modules if key == 'app.application.engine.nodes' or key.startswith('app.application.engine.nodes.')]))"],
            cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "backend")),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), [])


class GraphPreparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_filtered_required_producer_fails_input_preparation(self):
        graph = GraphTests()
        graph.setUp()
        graph.python(tasks=(TaskType.SCENE_COMBAT,))
        contract = replace(LEAF_CONTRACT, reads=(REQUIRED_LEAF,))
        graph.registry.register_python(TypedPythonNode, FakeExecutor, contract)
        node = TypedPythonNode(request_value=1, deps=(NodeId("producer"),))
        graph.bindings.nodes[node.id] = node
        plan = graph.plan()
        self.assertNotIn("producer", plan.nodes)
        # The A1.2 test read port has no Output; no catalog implementation is
        # substituted or fabricated by the compiler to satisfy required reads.
        with self.assertRaises(LookupError):
            await plan.get(node.id, contract).node.prepare_input(FakeReadView())

    async def test_filtered_optional_producer_allows_absent_input(self):
        graph = GraphTests()
        graph.setUp()
        graph.python(tasks=(TaskType.SCENE_COMBAT,))
        contract = NodeContract(
            CompositeOutput, LeafOutput, ContractId("test.optional"), ContractVersion("1"),
            reads=(OPTIONAL_LEAF,),
        )
        graph.registry.register_python(GraphOptionalConsumer, FakeExecutor, contract)
        node = GraphOptionalConsumer(id=GraphOptionalConsumer.id, deps=(NodeId("producer"),))
        graph.bindings.nodes[node.id] = node
        plan = graph.plan()
        self.assertNotIn("producer", plan.nodes)
        input_value = await plan.get(node.id, contract).node.prepare_input(FakeReadView())
        self.assertEqual(input_value.leaves, ())
