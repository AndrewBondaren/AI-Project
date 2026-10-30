"""A2.2: actual read versions, absence and transitive invalidation."""

import gc
import unittest
import weakref

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.context.resultInvalidation import ResultInvalidation
from app.application.engine.runtime.graphs.graphCompiler import GraphCompiler
from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision,
)
from app.dataModel.engine.dag.records import DomainReadEvidence, OutputRecord
from tests.dag_typing.fixtures import (
    FakeExecutor, GraphBindings, GraphConsumer, GraphPeer, GraphProducer, GraphRuleState,
    LeafOutput, NodeInput, TypedPythonNode,
)


def required(node):
    return RequiredOutput(OutputRef(NodeId(node), LeafOutput))


def optional(node):
    return OptionalOutput(OutputRef(NodeId(node), LeafOutput))


class InvalidationTests(unittest.TestCase):
    def setUp(self):
        self.make_catalog()

    def make_catalog(self, producer_reads=()):
        registry = NodeRegistry()
        self.contracts = {}
        for cls, reads in (
            (GraphProducer, producer_reads),
            (GraphPeer, (required("producer"), optional("producer"))),
            (GraphConsumer, (required("producer"), required("peer"), optional("peer"))),
            (TypedPythonNode, (required("peer"), required("consumer"))),
        ):
            contract = NodeContract(NodeInput, LeafOutput, ContractId("test." + cls.id), ContractVersion("1"), reads, error_types=())
            registry.register_python(cls, FakeExecutor, contract)
            self.contracts[cls.id] = contract
        self.catalog = DAGContext(ExecutionId("execution-1"), registry)

    def begin(self, node):
        return self.catalog.begin_attempt(NodeId(node), PlanRevision("plan-1"))

    def record(self, identity, reads=(), domains=(), output=None):
        contract = self.contracts[identity.node_id]
        return OutputRecord[LeafOutput](
            identity=identity, contract_id=contract.contract_id, contract_version=contract.version,
            output=LeafOutput(value=identity.attempt) if output is None else output,
            reads=reads, domain_reads=domains,
        )

    def published(self, node, requests=(), domains=(), output=None):
        identity = self.begin(node)
        view = self.catalog.read_view(NodeId(node))
        for request in requests:
            if isinstance(request, RequiredOutput):
                view.require(request)
            else:
                view.optional(request)
        self.catalog.publish(self.record(identity, view.dependency_reads, domains, output))
        return identity

    def current(self):
        return {identity.node_id for identity in self.catalog.current_outputs}

    def chain(self):
        self.published("producer")
        self.published("peer", (required("producer"),))
        self.published("consumer", (required("peer"),))
        self.published("typed-python", (required("consumer"),))

    def test_begin_invalidates_entire_chain_before_new_result_exists(self):
        self.chain()
        self.begin("producer")
        self.assertEqual(self.current(), set())
        with self.assertRaises(LookupError):
            self.catalog.read_view(NodeId("typed-python")).require(required("consumer"))

    def test_diamond_invalidates_both_branches_and_shared_consumer(self):
        self.published("producer")
        self.published("peer", (required("producer"),))
        self.published("consumer", (required("producer"),))
        self.published("typed-python", (required("peer"), required("consumer")))
        self.begin("producer")
        self.assertEqual(self.current(), set())

    def test_rerun_of_middle_node_preserves_upstream(self):
        self.chain()
        self.begin("peer")
        self.assertEqual(self.current(), {"producer"})

    def test_unread_declared_dependencies_do_not_invalidate(self):
        self.published("producer")
        self.published("consumer")
        self.published("typed-python", (required("consumer"),))
        self.begin("producer")
        self.assertEqual(self.current(), {"consumer", "typed-python"})

    def test_compiled_order_only_dependency_does_not_invalidate(self):
        registry = NodeRegistry()
        bindings = GraphBindings()
        for cls, deps in ((GraphProducer, ()), (GraphConsumer, (NodeId("producer"),))):
            contract = NodeContract(NodeInput, LeafOutput, ContractId("test." + cls.id), ContractVersion("1"), (), error_types=())
            registry.register_python(cls, FakeExecutor, contract)
            self.contracts[cls.id] = contract
            bindings.nodes[cls.id] = cls(id=cls.id, deps=deps)
        compiler = GraphCompiler(registry, bindings, compile_rules=lambda rules: (), evaluate_rules=lambda node, state: True)
        compiler.precompile()
        self.assertEqual(compiler.compile(GraphRuleState()).pre_llm_levels, (("producer",), ("consumer",)))
        self.catalog = DAGContext(ExecutionId("execution-1"), registry)
        self.published("producer")
        self.published("consumer")
        self.begin("producer")
        self.assertEqual(self.current(), {"consumer"})

    def test_only_actual_branch_is_invalidated(self):
        self.published("producer")
        self.published("peer")
        self.published("consumer", (required("peer"),))
        self.published("typed-python", (required("consumer"),))
        self.begin("producer")
        self.assertEqual(self.current(), {"peer", "consumer", "typed-python"})
        self.begin("peer")
        self.assertEqual(self.current(), set())

    def test_optional_presence_is_invalidated_on_removal(self):
        self.published("peer")
        self.published("consumer", (optional("peer"),))
        self.begin("peer")
        self.assertEqual(self.current(), set())

    def test_optional_absence_survives_begin_but_not_first_publication(self):
        self.published("consumer", (optional("peer"),))
        self.published("typed-python", (required("consumer"),))
        peer = self.begin("peer")
        self.assertEqual(self.current(), {"consumer", "typed-python"})
        self.catalog.publish(self.record(peer))
        self.assertEqual(self.current(), {"peer"})

    def test_optional_absence_survives_failed_attempt_without_output(self):
        consumer = self.published("consumer", (optional("peer"),))
        self.catalog.close_attempt(self.begin("peer"))
        self.assertEqual(self.catalog.current_outputs, (consumer,))

    def test_invalidated_payloads_never_return_after_failed_or_successful_rerun(self):
        self.chain()
        self.catalog.close_attempt(self.begin("producer"))
        self.assertEqual(self.current(), set())
        self.published("producer")
        self.assertEqual(self.current(), {"producer"})
        self.assertEqual(len(self.catalog.closed_attempts), 6)

    def test_identical_payload_still_has_new_result_version(self):
        output = LeafOutput(value=1)
        first = self.published("producer", output=output)
        self.published("peer", (required("producer"),))
        second = self.published("producer", output=output)
        self.assertNotEqual(first, second)
        self.assertEqual(self.current(), {"producer"})

    def test_old_snapshot_keeps_value_but_cannot_publish_after_transitive_change(self):
        self.chain()
        attempt = self.begin("typed-python")
        view = self.catalog.read_view(NodeId("typed-python"))
        output = view.require(required("consumer"))
        self.begin("producer")
        self.assertIs(view.require(required("consumer")), output)
        with self.assertRaisesRegex(RuntimeError, "no longer current"):
            self.catalog.publish(self.record(attempt, view.dependency_reads))
        self.catalog.close_attempt(attempt)
        self.assertEqual(self.current(), set())

    def test_invalid_attempt_and_rejected_publication_do_not_invalidate(self):
        consumer = self.published("consumer", (optional("peer"),))
        with self.assertRaises(ValueError):
            self.catalog.begin_attempt(NodeId("consumer"), PlanRevision(""))
        peer = self.begin("peer")
        record = self.record(peer).model_copy(update={"contract_version": ContractVersion("wrong")})
        with self.assertRaises(TypeError):
            self.catalog.publish(record)
        self.assertEqual(self.catalog.current_outputs, (consumer,))
        self.catalog.publish(self.record(peer))
        self.assertEqual(self.current(), {"peer"})

    def test_publication_cascade_cannot_publish_candidate_with_invalidated_reads(self):
        # GraphCompiler rejects such cyclic declarations before execution;
        # this also verifies atomicity of the low-level catalog primitive.
        self.make_catalog((optional("consumer"),))
        self.published("producer", (optional("consumer"),))
        consumer = self.begin("consumer")
        view = self.catalog.read_view(NodeId("consumer"))
        view.require(required("producer"))
        with self.assertRaisesRegex(RuntimeError, "after invalidation"):
            self.catalog.publish(self.record(consumer, view.dependency_reads))
        self.assertEqual(self.current(), {"producer"})
        self.catalog.close_attempt(consumer)

    def test_invalidation_does_not_keep_payloads_in_service_or_history(self):
        self.published("producer")
        payload = LeafOutput(value=42)
        ref = weakref.ref(payload)
        self.published("peer", (required("producer"),), output=payload)
        del payload
        self.begin("producer")
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(len(self.catalog.closed_attempts), 2)

    def test_domain_reuse_requires_all_concrete_matching_confirmations(self):
        domains = (
            DomainReadEvidence(domain="world", revision=DomainRevision("r1")),
            DomainReadEvidence(domain="climate", revision=DomainRevision("c1")),
        )
        self.published("producer", domains=domains)
        self.published("peer", (required("producer"),))
        self.assertEqual(self.catalog.invalidate_for_reuse({"world": DomainRevision("r1"), "climate": DomainRevision("c1")}), ())
        removed = self.catalog.invalidate_for_reuse({"world": DomainRevision("r1")})
        self.assertEqual({identity.node_id for identity in removed}, {"producer", "peer"})
        self.assertEqual(self.current(), set())

    def test_unknown_or_changed_domain_revision_invalidates_transitively(self):
        for recorded, confirmed in ((None, DomainRevision("r1")), (DomainRevision("r1"), DomainRevision("r2"))):
            with self.subTest(recorded=recorded, confirmed=confirmed):
                self.make_catalog()
                self.published("producer", domains=(DomainReadEvidence(domain="world", revision=recorded),))
                self.published("peer", (required("producer"),))
                self.catalog.invalidate_for_reuse({"world": confirmed})
                self.assertEqual(self.current(), set())

    def test_reuse_without_domain_reads_needs_no_confirmation(self):
        self.chain()
        before = self.catalog.current_outputs
        self.assertEqual(self.catalog.invalidate_for_reuse({}), ())
        self.assertEqual(self.catalog.current_outputs, before)

    def test_conflicting_domain_observations_cannot_be_confirmed_by_one_revision(self):
        self.published("producer", domains=(
            DomainReadEvidence(domain="world", revision=DomainRevision("r1")),
            DomainReadEvidence(domain="world", revision=DomainRevision("r2")),
        ))
        self.catalog.invalidate_for_reuse({"world": DomainRevision("r2")})
        self.assertEqual(self.current(), set())

    def test_pure_calculation_is_independent_of_mapping_order_and_never_mutates_inputs(self):
        self.chain()
        current = {identity.node_id: identity for identity in self.catalog.current_outputs}
        reads = {}
        for consumer, producer in (("peer", "producer"), ("consumer", "peer"), ("typed-python", "consumer")):
            view = self.catalog.read_view(NodeId(consumer))
            view.require(required(producer))
            reads[NodeId(consumer)] = view.dependency_reads
        saved = dict(current), dict(reads)
        for versions in (current, dict(reversed(tuple(current.items())))):
            affected = ResultInvalidation.affected(versions, reads, (NodeId("producer"),))
            self.assertEqual(affected, frozenset(current))
        self.assertEqual((current, reads), saved)
        self.assertEqual(len(self.current()), 4)
