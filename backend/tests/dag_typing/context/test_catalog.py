"""A2.1: attempts, fixed read snapshots, declarations and read evidence."""

from dataclasses import FrozenInstanceError, replace
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import weakref

from pydantic import BaseModel, ValidationError

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, DomainRevision, ExecutionId, NodeId, PlanRevision,
)
from app.dataModel.engine.dag.records import DependencyRead, OutputRecord
from tests.dag_typing.fixtures import (
    AlwaysLeafOutput, CompositeOutput, DerivedLeafOutput, FakeExecutor,
    GraphConsumer, GraphPeer, GraphProducer, LeafOutput, NodeInput,
)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.required = RequiredOutput(OutputRef(NodeId("producer"), LeafOutput))
        self.optional = OptionalOutput(OutputRef(NodeId("peer"), LeafOutput))
        self.registry = NodeRegistry()
        self.contracts = {}
        for cls, reads in ((GraphProducer, ()), (GraphPeer, ()), (GraphConsumer, (self.required, self.optional))):
            contract = NodeContract(NodeInput, LeafOutput, ContractId("test." + cls.id), ContractVersion("1"), reads, error_types=())
            self.registry.register_python(cls, FakeExecutor, contract)
            self.contracts[cls.id] = contract
        self.catalog = DAGContext(ExecutionId("execution-1"), self.registry)

    def begin(self, node="producer", revision="plan-1"):
        return self.catalog.begin_attempt(NodeId(node), PlanRevision(revision))

    def record(self, identity, output=None, **updates):
        payload = LeafOutput(value=identity.attempt) if output is None else output
        contract = self.contracts[identity.node_id]
        values = dict(identity=identity, contract_id=contract.contract_id, contract_version=contract.version, output=payload)
        values.update(updates)
        return OutputRecord[type(payload)](**values)

    def published(self, node="producer", output=None):
        identity = self.begin(node)
        self.catalog.publish(self.record(identity, output))
        return identity

    def snapshot(self, record, requirement):
        return PublishedDAGReadView(
            NodeId("consumer"), (requirement,),
            {reg.node_id: reg for reg in self.registry.graph_registrations()},
            {NodeId("producer"): record}, self.catalog.execution_id,
        )

    def test_execution_id_admission_reuses_strict_metadata_contract(self):
        for value in ("", " padded", 1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DAGContext(value, self.registry)

    def test_unknown_nodes_have_no_attempt_or_read_view(self):
        with self.assertRaises(KeyError):
            self.begin("unknown")
        with self.assertRaises(KeyError):
            self.catalog.read_view(NodeId("unknown"))
        self.assertEqual(self.catalog.attempt_counters, ())

    def test_attempt_counters_are_monotonic_per_node_across_plan_revisions(self):
        first = self.begin()
        peer = self.begin("peer")
        self.catalog.close_attempt(first)
        second = self.begin(revision="plan-2")
        self.assertEqual((first.attempt, peer.attempt, second.attempt), (1, 1, 2))
        self.assertEqual(first.execution_id, second.execution_id)
        self.assertEqual(second.plan_revision, PlanRevision("plan-2"))
        self.assertEqual(self.catalog.attempt_counters, (("peer", 1), ("producer", 2)))
        other = DAGContext(ExecutionId("execution-2"), self.registry).begin_attempt(NodeId("producer"), PlanRevision("plan-1"))
        self.assertNotEqual(first.result_key, other.result_key)

    def test_overlapping_attempts_of_one_node_are_rejected(self):
        self.begin()
        with self.assertRaisesRegex(RuntimeError, "open attempt"):
            self.begin()
        self.assertEqual(self.catalog.attempt_counters, (("producer", 1),))

    def test_invalid_revision_does_not_remove_previous_output_or_increment_counter(self):
        first = self.published()
        with self.assertRaises(ValidationError):
            self.begin(revision="")
        self.assertEqual(self.catalog.current_outputs, (first,))
        self.assertEqual(self.catalog.attempt_counters, (("producer", 1),))

    def test_required_and_optional_absence_are_recorded_with_registered_contract(self):
        view = self.catalog.read_view(NodeId("consumer"))
        with self.assertRaises(LookupError):
            view.require(self.required)
        self.assertIsNone(view.optional(self.optional))
        self.assertEqual(len(view.dependency_reads), 2)
        required, optional = view.dependency_reads
        self.assertTrue(required.required)
        self.assertFalse(optional.required)
        self.assertIsNone(required.result)
        self.assertIsNone(optional.result)
        self.assertEqual(required.contract_id, self.contracts[NodeId("producer")].contract_id)
        self.assertEqual(required.contract_version, ContractVersion("1"))

    def test_publication_preserves_payload_and_records_exact_read_identity(self):
        output = AlwaysLeafOutput(value=3)
        identity = self.published(output=output)
        view = self.catalog.read_view(NodeId("consumer"))
        self.assertIs(view.require(self.required), output)
        self.assertEqual(view.dependency_reads[0].result, identity)
        self.assertEqual(self.catalog.current_outputs, (identity,))
        self.assertEqual(self.catalog.closed_attempts, (identity,))

    def test_subclass_payload_is_compatible_with_declared_output(self):
        output = DerivedLeafOutput(value=3)
        self.published(output=output)
        self.assertIs(self.catalog.read_view(NodeId("consumer")).require(self.required), output)

    def test_unfinished_output_and_later_publication_are_invisible_to_existing_view(self):
        producer = self.begin()
        self.begin("consumer")
        local = self.record(producer)
        view = self.catalog.read_view(NodeId("consumer"))
        with self.assertRaises(LookupError):
            view.require(self.required)
        self.catalog.publish(local)
        with self.assertRaises(LookupError):
            view.require(self.required)
        self.assertEqual(len(view.dependency_reads), 1)
        self.assertIsNone(view.dependency_reads[0].result)
        self.assertIs(self.catalog.read_view(NodeId("consumer")).require(self.required), local.output)

    def test_optional_absence_stays_absent_for_the_lifetime_of_a_snapshot(self):
        view = self.catalog.read_view(NodeId("consumer"))
        self.published("peer")
        self.assertIsNone(view.optional(self.optional))
        self.assertIsInstance(self.catalog.read_view(NodeId("consumer")).optional(self.optional), LeafOutput)

    def test_read_evidence_is_local_and_identical_reads_are_deduplicated(self):
        self.published()
        first = self.catalog.read_view(NodeId("consumer"))
        second = self.catalog.read_view(NodeId("consumer"))
        first.require(self.required)
        first.require(self.required)
        first.optional(self.optional)
        first.optional(self.optional)
        self.assertEqual(len(first.dependency_reads), 2)
        self.assertEqual(second.dependency_reads, ())
        self.assertIsInstance(first.dependency_reads, tuple)

    def test_undeclared_producer_or_read_kind_is_forbidden(self):
        view = self.catalog.read_view(NodeId("consumer"))
        for call, request in (
            (view.require, RequiredOutput(OutputRef(NodeId("unknown"), LeafOutput))),
            (view.optional, OptionalOutput(self.required.ref)),
            (view.require, RequiredOutput(self.optional.ref)),
        ):
            with self.subTest(request=request), self.assertRaises(PermissionError):
                call(request)
        with self.assertRaises(TypeError):
            view.optional(self.required)
        with self.assertRaises(TypeError):
            view.require(self.optional)
        self.assertEqual(view.dependency_reads, ())

    def test_undeclared_output_type_is_error_even_for_optional_absence(self):
        view = self.catalog.read_view(NodeId("consumer"))
        for call, request in (
            (view.require, RequiredOutput(OutputRef(NodeId("producer"), CompositeOutput))),
            (view.optional, OptionalOutput(OutputRef(NodeId("peer"), CompositeOutput))),
        ):
            with self.subTest(request=request), self.assertRaises(TypeError):
                call(request)

    def test_unknown_declared_producer_is_not_optional_absence(self):
        registry = NodeRegistry()
        request = OptionalOutput(OutputRef(NodeId("unknown"), LeafOutput))
        contract = replace(self.contracts[NodeId("consumer")], reads=(request,))
        registry.register_python(GraphConsumer, FakeExecutor, contract)
        view = DAGContext(ExecutionId("execution-1"), registry).read_view(NodeId("consumer"))
        with self.assertRaises(KeyError):
            view.optional(request)

    def test_snapshot_rejects_version_execution_node_and_payload_mismatches(self):
        identity = self.begin()
        good = self.record(identity)
        optional = OptionalOutput(self.required.ref)
        records = (
            good.model_copy(update={"contract_version": ContractVersion("wrong")}),
            good.model_copy(update={"contract_id": ContractId("wrong")}),
            self.record(identity.model_copy(update={"execution_id": ExecutionId("foreign")})),
            self.record(identity.model_copy(update={"node_id": NodeId("peer")})),
            OutputRecord[BaseModel](identity=identity, contract_id=good.contract_id,
                                    contract_version=good.contract_version, output=CompositeOutput(leaves=())),
        )
        for record in records:
            with self.subTest(record=record):
                view = self.snapshot(record, optional)
                with self.assertRaises((TypeError, ValueError)):
                    view.optional(optional)
                self.assertEqual(view.dependency_reads, ())

    def test_snapshot_rejects_incompatible_declared_producer_contract(self):
        identity = self.begin()
        optional = OptionalOutput(OutputRef(NodeId("producer"), CompositeOutput))
        with self.assertRaises(TypeError):
            self.snapshot(self.record(identity), optional).optional(optional)

    def test_domain_evidence_records_values_without_fallback_or_collapsing_revisions(self):
        view = self.catalog.read_view(NodeId("consumer"))
        view.record_domain_read("test.domain", None)
        view.record_domain_read("test.domain", None)
        view.record_domain_read("test.domain", DomainRevision("r1"))
        self.assertEqual(len(view.domain_reads), 2)
        self.assertIsNone(view.domain_reads[0].revision)
        self.assertEqual(view.domain_reads[1].revision, DomainRevision("r1"))
        self.assertEqual(self.catalog.read_view(NodeId("consumer")).domain_reads, ())
        for domain, revision in (("", None), (" padded", None), ("test.domain", 1)):
            with self.assertRaises(ValidationError):
                view.record_domain_read(domain, revision)

    def test_views_are_frozen_have_no_catalog_write_api_and_do_not_repr_payload(self):
        self.published()
        view = self.catalog.read_view(NodeId("consumer"))
        for method in ("publish", "begin_attempt", "close_attempt"):
            self.assertFalse(hasattr(view, method))
        with self.assertRaises(FrozenInstanceError):
            view.consumer = NodeId("peer")
        self.assertNotIn("LeafOutput", repr(view))

    def test_rerun_removes_old_current_and_failure_does_not_revive_it(self):
        first = self.published()
        old_view = self.catalog.read_view(NodeId("consumer"))
        second = self.begin(revision="plan-2")
        self.assertEqual(second.attempt, 2)
        self.assertEqual(old_view.require(self.required).value, first.attempt)
        with self.assertRaises(LookupError):
            self.catalog.read_view(NodeId("consumer")).require(self.required)
        self.catalog.close_attempt(second)
        with self.assertRaises(LookupError):
            self.catalog.read_view(NodeId("consumer")).require(self.required)
        self.assertEqual(self.catalog.current_outputs, ())

    def test_closed_duplicate_and_late_attempts_cannot_publish(self):
        first = self.begin()
        record = self.record(first)
        self.catalog.publish(record)
        for action in (lambda: self.catalog.publish(record), lambda: self.catalog.close_attempt(first)):
            with self.assertRaises(RuntimeError):
                action()
        second = self.begin()
        with self.assertRaises(RuntimeError):
            self.catalog.publish(record)
        self.catalog.publish(self.record(second))

    def test_close_without_output_forbids_late_publication(self):
        identity = self.begin()
        self.catalog.close_attempt(identity)
        with self.assertRaises(RuntimeError):
            self.catalog.publish(self.record(identity))
        self.assertEqual(self.catalog.current_outputs, ())

    def test_wrong_execution_revision_or_attempt_does_not_poison_open_attempt(self):
        identity = self.begin()
        for update in (
            {"execution_id": ExecutionId("foreign")}, {"plan_revision": PlanRevision("other")}, {"attempt": 9},
        ):
            with self.subTest(update=update), self.assertRaises((ValueError, RuntimeError)):
                self.catalog.publish(self.record(identity.model_copy(update=update)))
        self.catalog.publish(self.record(identity))
        self.assertEqual(self.catalog.current_outputs, (identity,))

    def test_publication_rejects_wrong_contract_payload_and_forged_record_metadata(self):
        identity = self.begin()
        good = self.record(identity)
        records = (
            good.model_copy(update={"contract_id": ContractId("wrong")}),
            good.model_copy(update={"contract_version": ContractVersion("2")}),
            self.record(identity, CompositeOutput(leaves=())),
            good.model_copy(update={"contract_version": 1}),
            LeafOutput(value=1),
        )
        for record in records:
            with self.subTest(record=record), self.assertRaises((TypeError, ValueError)):
                self.catalog.publish(record)
        self.assertEqual(self.catalog.current_outputs, ())
        self.catalog.publish(good)

    def test_publication_does_not_repeat_output_schema_or_domain_validation(self):
        identity = self.begin()
        record = self.record(identity)
        with patch.object(LeafOutput, "model_validate", side_effect=AssertionError("not catalog ownership")):
            self.catalog.publish(record)

    def test_stale_read_version_cannot_publish_but_fresh_view_can(self):
        self.published()
        consumer = self.begin("consumer")
        old = self.catalog.read_view(NodeId("consumer"))
        old.require(self.required)
        second = self.begin()
        self.catalog.publish(self.record(second))
        with self.assertRaisesRegex(RuntimeError, "no longer current"):
            self.catalog.publish(self.record(consumer, reads=old.dependency_reads))
        self.assertNotIn(consumer, self.catalog.current_outputs)
        fresh = self.catalog.read_view(NodeId("consumer"))
        fresh.require(self.required)
        self.catalog.publish(self.record(consumer, reads=fresh.dependency_reads))

    def test_changed_optional_absence_cannot_publish(self):
        consumer = self.begin("consumer")
        view = self.catalog.read_view(NodeId("consumer"))
        self.assertIsNone(view.optional(self.optional))
        self.published("peer")
        with self.assertRaisesRegex(RuntimeError, "no longer current"):
            self.catalog.publish(self.record(consumer, reads=view.dependency_reads))

    def test_publication_rejects_undeclared_or_wrong_version_read_evidence(self):
        producer = self.published()
        consumer = self.begin("consumer")
        contract = self.contracts[NodeId("producer")]
        good = DependencyRead(producer=NodeId("producer"), contract_id=contract.contract_id,
                              contract_version=contract.version, required=True, result=producer)
        for read, error in (
            (good.model_copy(update={"required": False}), PermissionError),
            (good.model_copy(update={"contract_version": ContractVersion("2")}), TypeError),
        ):
            with self.assertRaises(error):
                self.catalog.publish(self.record(consumer, reads=(read,)))
        self.catalog.publish(self.record(consumer, reads=(good,)))

    def test_closed_history_does_not_retain_payload_after_rerun(self):
        output = LeafOutput(value=3)
        ref = weakref.ref(output)
        identity = self.published(output=output)
        del output
        self.begin()
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(self.catalog.closed_attempts, (identity,))

    def test_registry_bindings_are_fixed_for_this_execution(self):
        from tests.dag_typing.fixtures import GraphDerivedProducer
        contract = NodeContract(NodeInput, DerivedLeafOutput, ContractId("extra"), ContractVersion("1"), (), error_types=())
        self.registry.register_python(GraphDerivedProducer, FakeExecutor, contract)
        with self.assertRaises(KeyError):
            self.begin("derived-producer")

    def test_target_context_import_does_not_load_production_nodes(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run(
            [sys.executable, "-c", "import sys,json; from app.application.engine.runtime.dag.context.dagContext import DAGContext; print(json.dumps([name for name in sys.modules if name == 'app.application.engine.nodes' or name.startswith('app.application.engine.nodes.')]))"],
            cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "backend")),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
