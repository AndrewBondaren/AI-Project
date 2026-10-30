"""A1.1: metadata invariants, immutable payload admission and status ownership."""

import ast
import json
from pathlib import Path
import unittest

from pydantic import BaseModel, ConfigDict, ValidationError

from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationSource, ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity,
)
from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, ExecutionIdentity, NodeId,
)
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence, OutputRecord
from app.dataModel.engine.dag.snapshotMetadata import SnapshotMetadata
from tests.dag_typing.fixtures import CompositeOutput, LeafOutput, identity


class MetadataTests(unittest.TestCase):
    def read(self, result=None, required=False):
        return DependencyRead(
            producer=NodeId("producer"), contract_id=ContractId("test.output"),
            contract_version=ContractVersion("1"), required=required, result=result,
        )

    def record(self, output, **kwargs):
        return OutputRecord[type(output)](
            identity=identity("consumer"), contract_id=ContractId("test.output"),
            contract_version=ContractVersion("1"), output=output, **kwargs,
        )

    def snapshot(self, **kwargs):
        values = dict(
            format_version=1, execution_id="execution-1", plan_revision="plan-1",
            pass_number=0, contract_versions=(("test.output", "1"),),
            attempt_counters=(("producer", 2),),
        )
        values.update(kwargs)
        return SnapshotMetadata(**values)

    def test_identity_is_frozen_and_revision_is_not_result_address(self):
        value = identity()
        other = ExecutionIdentity(**{**value.model_dump(), "plan_revision": "plan-2"})
        self.assertEqual(value.result_key, other.result_key)
        self.assertNotEqual(value.result_key, identity(attempt=2).result_key)
        with self.assertRaises(ValidationError):
            value.attempt = 3
        self.assertEqual(value, ExecutionIdentity.model_validate_json(value.model_dump_json()))

    def test_identity_rejects_empty_ids_coercion_and_invalid_attempts(self):
        for field in ("execution_id", "node_id", "plan_revision"):
            for bad in ("", " ", " trailing ", 123):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValidationError):
                    ExecutionIdentity(**{**identity().model_dump(), field: bad})
        for bad in (0, -1, True, "1", 1.5):
            with self.subTest(attempt=bad), self.assertRaises(ValidationError):
                identity(attempt=bad)

    def test_composed_payload_and_nested_instances_are_shared_without_copy(self):
        leaf = LeafOutput(value=7)
        output = CompositeOutput(leaves=(leaf,))
        record = self.record(output)
        self.assertIs(record.output, output)
        self.assertIs(record.output.leaves[0], leaf)
        with self.assertRaises(ValidationError):
            record.output.leaves[0].value = 9

    def test_mutable_nested_model_is_rejected_even_under_frozen_outer(self):
        class MutableOutput(BaseModel):
            values: list[int]

        class FrozenOuter(BaseModel):
            model_config = ConfigDict(frozen=True)
            inner: MutableOutput

        with self.assertRaises(ValidationError):
            self.record(FrozenOuter(inner=MutableOutput(values=[1])))
        with self.assertRaises(ValidationError):
            self.record(MutableOutput(values=[1]))

    def test_frozen_model_with_mutable_container_is_rejected(self):
        class FrozenList(BaseModel):
            model_config = ConfigDict(frozen=True)
            values: list[int]

        with self.assertRaises(ValidationError):
            self.record(FrozenList(values=[1]))

    def test_wrong_payload_type_and_raw_dict_are_rejected(self):
        for output in ({"value": 1}, CompositeOutput(leaves=())):
            with self.subTest(output=output), self.assertRaises(ValidationError):
                OutputRecord[LeafOutput](
                    identity=identity(), contract_id=ContractId("test.output"),
                    contract_version=ContractVersion("1"), output=output,
                )

    def test_absence_is_evidence_but_not_successful_required_input(self):
        optional = self.read()
        self.assertIsNone(self.record(LeafOutput(value=1), reads=(optional,)).reads[0].result)
        with self.assertRaises(ValidationError):
            self.record(LeafOutput(value=1), reads=(self.read(required=True),))

    def test_read_identity_must_match_producer_and_execution(self):
        with self.assertRaises(ValidationError):
            self.read(identity("other"))
        foreign = ExecutionIdentity(**{**identity().model_dump(), "execution_id": "other-run"})
        with self.assertRaises(ValidationError):
            self.record(LeafOutput(value=1), reads=(self.read(foreign),))
        self.record(LeafOutput(value=1), reads=(self.read(identity(), required=True),))

    def test_domain_evidence_distinguishes_unknown_revision(self):
        evidence = DomainReadEvidence(domain="terrain", revision=None)
        self.assertIsNone(evidence.revision)
        with self.assertRaises(ValidationError):
            DomainReadEvidence(domain="terrain", revision="")

    def test_snapshot_versions_and_counters_round_trip_without_ambiguity(self):
        snapshot = self.snapshot()
        restored = SnapshotMetadata.model_validate_json(snapshot.model_dump_json())
        self.assertEqual(snapshot, restored)
        for update in (
            {"format_version": True}, {"pass_number": -1},
            {"attempt_counters": (("producer", 0),)},
            {"contract_versions": (("test.output", "1"), ("test.output", "2"))},
            {"attempt_counters": (("producer", 1), ("producer", 2))},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                self.snapshot(**update)

    def test_cancel_event_requires_explanation_and_cannot_hold_payload(self):
        fields = dict(
            identity=identity(), pass_number=0, phase="pre_llm", level=0,
            timestamp=1.0, code=ExecutionEventCode.CANCEL_OBSERVED,
            severity=ExecutionSeverity.WARNING, status=NodeStatus.CANCELLED,
            message="cancelled", requirements=(("producer", "test.output", "1", True),),
        )
        with self.assertRaises(ValidationError):
            ExecutionDiagnostic(**fields)
        event = ExecutionDiagnostic(
            **fields, cancel_source=CancellationSource.UNKNOWN,
            cancel_reason=CancellationReason.UNKNOWN,
        )
        self.assertIsNone(event.cancel_message)
        self.assertEqual(event, ExecutionDiagnostic.model_validate_json(event.model_dump_json()))
        with self.assertRaises(ValidationError):
            ExecutionDiagnostic(**{**event.model_dump(), "output": LeafOutput(value=1)})

    def test_cancellation_codes_are_strict_and_message_is_only_explanation(self):
        event = ExecutionDiagnostic(
            identity=identity(), pass_number=0, phase="pre_llm", level=0,
            timestamp=1.0, code=ExecutionEventCode.CANCEL_OBSERVED,
            severity=ExecutionSeverity.WARNING, status=NodeStatus.CANCELLED,
            message="cancelled", cancel_source=CancellationSource.USER,
            cancel_reason=CancellationReason.REQUESTED, cancel_message="Stop this run, please",
        )
        restored = ExecutionDiagnostic.model_validate_json(event.model_dump_json())
        self.assertIs(restored.cancel_source, CancellationSource.USER)
        self.assertIs(restored.cancel_reason, CancellationReason.REQUESTED)
        self.assertEqual(restored.cancel_message, event.cancel_message)
        for field in ("cancel_source", "cancel_reason"):
            for bad in ("unknown", "arbitrary", None):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValidationError):
                    ExecutionDiagnostic(**{**event.model_dump(), field: bad})
            wire = json.loads(event.model_dump_json())
            wire[field] = "arbitrary"
            with self.subTest(wire_field=field), self.assertRaises(ValidationError):
                ExecutionDiagnostic.model_validate_json(json.dumps(wire))

    def test_non_cancel_event_does_not_require_cancellation_metadata(self):
        event = ExecutionDiagnostic(
            identity=identity(), pass_number=0, phase="pre_llm", level=0,
            timestamp=1.0, code=ExecutionEventCode.NODE_STARTED,
            severity=ExecutionSeverity.INFO, status=NodeStatus.RUNNING, message="started",
        )
        self.assertIsNone(event.cancel_source)
        self.assertIsNone(event.cancel_reason)
        self.assertIsNone(event.cancel_message)

    def test_single_status_owner_and_data_model_has_no_application_imports(self):
        backend = Path(__file__).resolve().parents[3]
        old = backend / "app/application/engine/nodes/nodeStatus.py"
        self.assertFalse(old.exists())
        self.assertEqual(NodeStatus.SUCCESS.value, "success")
        self.assertEqual(NodeStatus.CANCELLED.value, "cancelled")
        self.assertEqual(NodeStatus.GATED.value, "gated")
        consumer = backend / "app/application/engine/nodes/nodeRuntimeState.py"
        self.assertIn("from app.dataModel.engine.dag.nodeStatus import NodeStatus", consumer.read_text())
        for path in (backend / "app/dataModel/engine/dag").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(("app.application", "app.db", "app.core")))


if __name__ == "__main__":
    unittest.main()
