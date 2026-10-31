"""A3.4: explicit validation/provenance, DSL patches and repair wire modes."""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.llmValidator import LLMValidator
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.identity import ExecutionIdentity, ExecutionId, NodeId, PlanRevision, ContractId, ContractVersion, DomainRevision
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence
from tests.dag_typing.fixtures import CompositeOutput, LeafOutput, NodeInput, RecordingValidator
from tests.dag_typing.llm import test_payload as payloads


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.case = payloads.PayloadTests()
        self.case.setUp()
        self.resolver = self.case.builder._dsl_resolver
        self.projector = DSLFailureProjector(self.resolver)
        self.builder = RepairBuilder(self.resolver)
        self.node = replace(self.case.node, dsl_patches={"bad": "patch"})
        self.case.dsl.texts["explicit"] = "Explicit patch"
        self.identity = ExecutionIdentity(execution_id=ExecutionId("repair-exec"), node_id=self.node.id,
                                          attempt=2, plan_revision=PlanRevision("p1"))
        self.validation = ValidationResult(status=ValidationStatus.RETRY, errors=[
            NodeValidationError(code="bad", message="Invalid field", severity=NodeErrorSeverity.RETRY, field="value"),
        ])
        self.base = self.case.payload(self.case.section())

    def failure(self, **kwargs):
        args = {"raw_output": '{"value":"bad"}', **kwargs}
        return self.projector.project(self.node, self.case.registration, self.identity, self.validation, **args)

    def test_typed_failure_retains_native_validation_identity_and_reads(self):
        producer = self.identity.model_copy(update={"node_id": NodeId("producer")})
        read = DependencyRead(producer=producer.node_id, contract_id=ContractId("producer"),
                              contract_version=ContractVersion("1"), required=True, result=producer)
        domain = DomainReadEvidence(domain="world", revision=DomainRevision("r1"))
        failure = self.failure(reads=(read,), domain_reads=(domain,), pass_number=3, repair_attempt=4)
        self.assertIs(failure.validation, self.validation)
        self.assertIs(failure.identity, self.identity)
        self.assertIs(failure.reads[0], read)
        wire = failure.to_dict()
        self.assertEqual(wire["identity"]["attempt"], 2)
        self.assertEqual(wire["pass_number"], 3)
        self.assertEqual(wire["repair_attempt"], 4)
        self.assertEqual(wire["reads"][0]["result"]["node_id"], "producer")
        self.assertEqual(wire["domain_reads"][0]["revision"], "r1")
        self.assertEqual(wire["validation"]["errors"][0]["field"], "value")
        with self.assertRaises(FrozenInstanceError):
            failure.raw_output = "{}"

    def test_native_dsl_patch_selection_and_dedup_keep_current_keys(self):
        self.validation.errors.append(self.validation.errors[0])
        self.validation.dsl_patch = ["explicit", "patch"]
        failure = self.failure(dsl_keys=("node", "patch"))
        self.assertEqual(failure.dsl_keys, ("node", "patch", "explicit"))
        payload = self.builder.build(self.base, (failure,))
        self.assertEqual(payload.sections[0].dsl, "Use ru\n\nRepair instruction\n\nExplicit patch")
        self.assertEqual(self.validation.dsl_patch, ["explicit", "patch"])

    def test_patch_mapping_is_immutable_private_copy(self):
        patches = {"bad": "patch"}
        node = replace(self.node, dsl_patches=patches)
        patches["bad"] = "explicit"
        self.assertEqual(node.dsl_patches["bad"], "patch")
        with self.assertRaises(TypeError):
            node.dsl_patches["bad"] = "explicit"
        with self.assertRaises(ValidationError):
            replace(node, dsl_patches={"bad": 7})

    def test_maximum_wire_has_failed_sections_schema_and_original_input_ref(self):
        original = self.base.sections[0].input
        with patch.object(NodeInput, "model_dump", side_effect=AssertionError("eager dump")), \
             patch.object(NodeInput, "__deepcopy__", side_effect=AssertionError("copy")):
            payload = self.builder.build(self.base, (self.failure(),))
        self.assertIs(payload.sections[0].input, original)
        self.assertEqual(self.base.sections[0].dsl, "Use ru")
        full, user = payload.to_dict(), payload.to_user_dict()
        self.assertEqual(full.pop("dsl"), self.base.global_dsl)
        self.assertEqual(full, user)
        self.assertEqual(full["type"], "repair")
        self.assertEqual(full["errors"][0]["output"], {"value": "bad"})
        self.assertEqual(set(full["response_format"]["properties"]), {self.node.id})

    def test_economy_wire_only_contains_errors_but_schema_is_available_to_client(self):
        payload = self.builder.build(self.base, (self.failure(),), mode=RepairMode.ECONOMY)
        self.assertEqual(set(payload.to_dict()), {"type", "errors"})
        self.assertEqual(payload.to_dict(), payload.to_user_dict())
        self.assertEqual(set(payload.response_format_schema["properties"]), {self.node.id})
        json.dumps(payload.to_dict())

    def test_raw_invalid_json_missing_section_and_scalar_are_transport_only(self):
        for raw, expected in (("{broken", "{broken"), (None, None), ("null", None), ("7", 7)):
            with self.subTest(raw=raw):
                failure = self.failure(raw_output=raw)
                self.assertEqual(failure.to_dict()["output"], expected)
                self.assertEqual(failure.raw_output, raw)

    def test_only_failed_sections_are_requested_and_input_is_not_reprepared(self):
        other = replace(self.base.sections[0], node_id=NodeId("success"))
        base = self.case.payload(self.base.sections[0], other)
        with patch.object(type(self.node), "prepare_input", side_effect=AssertionError("prepare")):
            payload = self.builder.build(base, (self.failure(),))
        self.assertEqual(len(base.sections), 2)
        self.assertEqual(len(payload.sections), 1)

    def test_multiple_failure_order_is_explicit_and_schema_covers_each(self):
        second = replace(self.base.sections[0], node_id=NodeId("second"))
        base = self.case.payload(self.base.sections[0], second)
        first = self.failure()
        other = replace(first, identity=replace_identity(first.identity, node_id=second.node_id))
        payload = self.builder.build(base, (other, first))
        self.assertEqual([section.node_id for section in payload.sections], [second.node_id, self.node.id])

    def test_wrong_node_schema_and_duplicate_failures_are_rejected(self):
        first = self.failure()
        with self.assertRaises(KeyError):
            self.builder.build(self.base, (replace(first, identity=replace_identity(first.identity, node_id=NodeId("absent"))),))
        with self.assertRaises(TypeError):
            self.builder.build(self.base, (replace(first, output_type=CompositeOutput),))
        with self.assertRaises(ValueError):
            self.builder.build(self.base, (first, first))
        with self.assertRaises(ValueError):
            self.builder.build(self.base, ())

    def test_mixed_execution_pass_and_repair_iteration_are_rejected(self):
        second_section = replace(self.base.sections[0], node_id=NodeId("second"))
        base = self.case.payload(self.base.sections[0], second_section)
        first = self.failure()
        second = replace(first, identity=replace_identity(first.identity, node_id=second_section.node_id))
        variants = (replace(second, pass_number=1), replace(second, repair_attempt=1),
                    replace(second, identity=replace_identity(second.identity, execution_id=ExecutionId("other"))))
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, "mixed execution"):
                self.builder.build(base, (first, variant))

    def test_success_validation_negative_indices_and_raw_dict_are_rejected(self):
        for validation in (ValidationResult(status=ValidationStatus.OK),):
            with self.assertRaises(ValueError):
                self.projector.project(self.node, self.case.registration, self.identity, validation, raw_output=None)
        for kwargs in ({"pass_number": -1}, {"repair_attempt": True}, {"raw_output": {"value": 1}}, {"dsl_keys": ["node"]}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                self.failure(**kwargs)

    def test_foreign_read_identity_and_node_binding_are_rejected(self):
        with self.assertRaises(TypeError):
            self.projector.project(self.node, self.case.registration,
                                   replace_identity(self.identity, node_id=NodeId("foreign")), self.validation, raw_output=None)
        producer = replace_identity(self.identity, execution_id=ExecutionId("other"))
        read = DependencyRead(producer=producer.node_id, contract_id=ContractId("x"),
                              contract_version=ContractVersion("1"), required=True, result=producer)
        with self.assertRaisesRegex(ValueError, "another execution"):
            self.failure(reads=(read,))

    def test_semantic_validator_result_and_hook_survive_projection(self):
        hook = RecordingValidator[LeafOutput](self.validation)
        contract = replace(self.case.contract, validator=hook)
        output, validation = LLMValidator(ContractValidator(), NodeValidator()).validate('{"value":1}', contract, self.identity, repair_attempt=2)
        self.assertIsNone(output)
        self.assertEqual(len(hook.contexts), 1)
        self.assertEqual(hook.contexts[0].repair_attempt, 2)
        self.assertIs(validation, self.validation)
        failure = self.projector.project(self.node, replace(self.case.registration, contract=contract), self.identity,
                                         validation, raw_output='{"value":1}', repair_attempt=2)
        self.assertIs(failure.validation, validation)
        self.assertEqual(self.builder.build(self.base, (failure,)).errors[0].repair_attempt, 2)

    def test_repair_mode_is_existing_enum_and_reserved_keys_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.builder.build(self.base, (self.failure(),), mode="maximum")
        failure = self.failure()
        base = self.case.payload(replace(self.base.sections[0], node_id=NodeId("errors")))
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.builder.build(base, (replace(failure, identity=replace_identity(failure.identity, node_id=NodeId("errors"))),))

    def test_target_import_does_not_load_legacy_repair_or_production_nodes(self):
        root = Path(__file__).resolve().parents[4]
        code = """
import sys
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
assert not any(k.startswith('app.application.engine.nodes') for k in sys.modules)
assert 'app.application.engine.repair.repairBuilder' not in sys.modules
assert 'app.application.engine.repair.repairOrchestrator' not in sys.modules
assert 'app.core.container.engine' not in sys.modules
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=root,
                                env={**os.environ, "PYTHONPATH": str(root / "backend")},
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def replace_identity(identity, **kwargs):
    return ExecutionIdentity.model_validate({**vars(identity), **kwargs})
