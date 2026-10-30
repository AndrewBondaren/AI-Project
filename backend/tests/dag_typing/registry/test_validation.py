"""A1.4: schema admission, immutable identity and semantic delegation."""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.llmValidator import LLMValidator
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.nodeValidationError import NodeErrorSeverity, NodeValidationError
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.dag.records import OutputRecord
from tests.dag_typing.fixtures import (
    AlwaysCompositeOutput, AlwaysLeafOutput, BoundedOutput, CompositeOutput,
    FrozenListOutput, LeafOutput, LeafTupleOutput, LEAF_CONTRACT, MutableBoundaryOutput,
    NodeInput, NormalizedOutput, RecordingValidator, TypedLLMNode, identity,
)


class ContractValidationTests(unittest.TestCase):
    def setUp(self):
        self.validator = ContractValidator()

    def test_existing_pojo_and_nested_models_are_admitted_without_replacing_instances(self):
        for output in (
            LeafOutput(value=2), CompositeOutput(leaves=(LeafOutput(value=3),)),
            AlwaysCompositeOutput(leaves=(AlwaysLeafOutput(value=4),)),
        ):
            with self.subTest(model=type(output)):
                nested = getattr(output, "leaves", None)
                admitted, result = self.validator.validate(output, type(output))
                self.assertTrue(result.ok)
                self.assertIs(admitted, output)
                self.assertIs(getattr(admitted, "leaves", None), nested)
                if nested:
                    self.assertIs(admitted.leaves[0], nested[0])

    def test_admitted_output_can_enter_record_as_the_same_pojo(self):
        output = LeafOutput(value=1)
        admitted, result = self.validator.validate(output, LeafOutput)
        self.assertTrue(result.ok)
        record = OutputRecord[LeafOutput](
            identity=identity(), contract_id=LEAF_CONTRACT.contract_id,
            contract_version=LEAF_CONTRACT.version, output=admitted,
        )
        self.assertIs(record.output, output)

    def test_ready_boundary_rejects_raw_transport_and_wrong_model_class(self):
        for value in ({"value": 1}, '{"value": 1}', CompositeOutput(leaves=()), None):
            with self.subTest(value=value):
                admitted, result = self.validator.validate(value, LeafOutput)
                self.assertIsNone(admitted)
                self.assertEqual(result.status, ValidationStatus.FAIL)
                self.assertEqual(result.errors[0].severity, NodeErrorSeverity.FAIL)

    def test_model_construct_cannot_bypass_pydantic_type_and_field_constraints(self):
        for value in (BoundedOutput.model_construct(value=-1), BoundedOutput.model_construct(value="secret-bad-input")):
            admitted, result = self.validator.validate(value, BoundedOutput)
            self.assertIsNone(admitted)
            self.assertFalse(result.ok)
            self.assertEqual(result.errors[0].code, "schema_mismatch")
            self.assertEqual(result.errors[0].field, "value")
            self.assertNotIn("secret-bad-input", result.errors[0].message)

    def test_nested_model_construct_is_checked_despite_pydantic_instance_trust(self):
        bad_leaf = LeafOutput.model_construct(value="bad")
        value = CompositeOutput.model_construct(leaves=(bad_leaf,))
        admitted, result = self.validator.validate(value, CompositeOutput)
        self.assertIsNone(admitted)
        self.assertFalse(result.ok)
        self.assertEqual(bad_leaf.value, "bad")

    def test_missing_default_and_extra_fields_are_not_silently_repaired(self):
        missing = BoundedOutput()
        missing.__dict__.pop("value")
        extra = BoundedOutput()
        extra.__dict__["unexpected"] = 1
        for value in (missing, extra):
            admitted, result = self.validator.validate(value, BoundedOutput)
            self.assertIsNone(admitted)
            self.assertFalse(result.ok)
        self.assertNotIn("value", vars(missing))

    def test_normalization_of_a_forged_ready_instance_is_rejected_without_mutation(self):
        value = NormalizedOutput.model_construct(text=" padded ")
        admitted, result = self.validator.validate(value, NormalizedOutput)
        self.assertIsNone(admitted)
        self.assertFalse(result.ok)
        self.assertEqual(value.text, " padded ")
        canonical = NormalizedOutput(text=" padded ")
        self.assertIs(self.validator.validate(canonical, NormalizedOutput)[0], canonical)

    def test_mutable_model_and_frozen_model_with_mutable_container_are_rejected(self):
        for value in (MutableBoundaryOutput(value=1), FrozenListOutput(leaves=[LeafOutput(value=1)])):
            admitted, result = self.validator.validate(value, type(value))
            self.assertIsNone(admitted)
            self.assertFalse(result.ok)

    def test_input_and_output_use_the_declared_pojo_constraints(self):
        value = NodeInput(value=4)
        self.assertIs(self.validator.validate(value, LEAF_CONTRACT.input_type)[0], value)
        self.assertIsNone(self.validator.validate(value, LEAF_CONTRACT.output_type)[0])
        invalid_input = NodeInput.model_construct(value="invalid")
        self.assertIsNone(self.validator.validate(invalid_input, LEAF_CONTRACT.input_type)[0])

    def test_json_defaults_and_normalization_belong_to_pydantic(self):
        default, result = self.validator.parse_json("{}", BoundedOutput)
        self.assertTrue(result.ok)
        self.assertEqual(default.value, BoundedOutput().value)
        normalized, result = self.validator.parse_json('{"text":" padded "}', NormalizedOutput)
        self.assertTrue(result.ok)
        self.assertEqual(normalized.text, "padded")

    def test_bad_json_schema_and_mutable_wire_results_are_retryable_without_output(self):
        for raw, contract, code in (
            ("{broken", LeafOutput, "invalid_json"),
            ('{"value":"secret-bad-input"}', LeafOutput, "schema_mismatch"),
            ('{"value":-1}', BoundedOutput, "schema_mismatch"),
            ('{"value":1,"extra":2}', LeafOutput, "schema_mismatch"),
            ('{"value":1}', MutableBoundaryOutput, "schema_mismatch"),
            ('{"leaves":[]}', FrozenListOutput, "schema_mismatch"),
        ):
            with self.subTest(raw=raw, contract=contract):
                output, result = self.validator.parse_json(raw, contract)
                self.assertIsNone(output)
                self.assertEqual(result.status, ValidationStatus.RETRY)
                self.assertEqual(result.errors[0].code, code)
                self.assertEqual(result.errors[0].severity, NodeErrorSeverity.RETRY)
                self.assertNotIn("secret-bad-input", result.errors[0].message)

    def test_ready_validation_does_not_serialize_or_deepcopy_payload(self):
        output = CompositeOutput(leaves=(LeafOutput(value=2),))
        with unittest.mock.patch.object(CompositeOutput, "model_dump", side_effect=AssertionError("no serialization")):
            self.assertIs(self.validator.validate(output, CompositeOutput)[0], output)

    def test_root_model_uses_its_root_schema_and_preserves_ready_instances(self):
        leaf = LeafOutput(value=3)
        value = LeafTupleOutput(root=(leaf,))
        admitted, result = self.validator.validate(value, LeafTupleOutput)
        self.assertTrue(result.ok)
        self.assertIs(admitted, value)
        self.assertIs(admitted.root[0], leaf)
        parsed, result = self.validator.parse_json('[{"value":3}]', LeafTupleOutput)
        self.assertTrue(result.ok)
        self.assertEqual(parsed.root[0].value, 3)
        invalid = LeafTupleOutput.model_construct(root=(LeafOutput.model_construct(value="bad"),))
        self.assertIsNone(self.validator.validate(invalid, LeafTupleOutput)[0])


class SemanticValidationTests(unittest.TestCase):
    def setUp(self):
        self.contract_validator = ContractValidator()
        self.node_validator = NodeValidator()
        self.llm_validator = LLMValidator(self.contract_validator, self.node_validator)

    def test_optional_callback_is_noop_and_valid_json_returns_pojo(self):
        contract = replace(LEAF_CONTRACT, reads=())
        output, result = self.llm_validator.validate('{"value":3}', contract, identity())
        self.assertTrue(result.ok)
        self.assertIsInstance(output, LeafOutput)
        self.assertEqual(output.value, 3)

    def test_registered_callback_receives_typed_output_and_identity_without_copies(self):
        result = ValidationResult(status=ValidationStatus.OK)
        callback = RecordingValidator[LeafOutput](result)
        contract = replace(LEAF_CONTRACT, validator=callback)
        registry = NodeRegistry()
        registry.register_llm(TypedLLMNode, contract)
        binding = registry.get(NodeId("typed-llm"), contract)
        attempt = identity("typed-llm")
        output, actual = self.llm_validator.validate(
            '{"value":2}', binding.contract, attempt, pass_number=4, repair_attempt=2,
        )
        self.assertIs(actual, result)
        self.assertEqual(len(callback.contexts), 1)
        ctx = callback.contexts[0]
        self.assertIs(ctx.output, output)
        self.assertIs(ctx.identity, attempt)
        self.assertEqual((ctx.pass_number, ctx.repair_attempt), (4, 2))

    def test_semantic_status_errors_and_dsl_patch_are_preserved(self):
        for status in (ValidationStatus.OK, ValidationStatus.RETRY, ValidationStatus.FAIL, ValidationStatus.USER_ERROR):
            with self.subTest(status=status):
                result = ValidationResult(
                    status=status,
                    errors=[NodeValidationError(code="test.domain", message="domain decision", severity=NodeErrorSeverity.USER_ERROR)],
                    dsl_patch=["domain-owned repair instruction"],
                )
                callback = RecordingValidator[LeafOutput](result)
                output, actual = self.llm_validator.validate(
                    '{"value":1}', replace(LEAF_CONTRACT, validator=callback), identity(),
                )
                self.assertIs(actual, result)
                self.assertIs(actual.errors, result.errors)
                self.assertIs(actual.dsl_patch, result.dsl_patch)
                if status is ValidationStatus.OK:
                    self.assertIs(output, callback.contexts[0].output)
                else:
                    self.assertIsNone(output)

    def test_semantic_callback_is_not_called_before_successful_schema_admission(self):
        callback = RecordingValidator[LeafOutput](ValidationResult(status=ValidationStatus.OK))
        for raw in ("broken", '{"value":"bad"}', '{"extra":1}'):
            output, result = self.llm_validator.validate(raw, replace(LEAF_CONTRACT, validator=callback), identity())
            self.assertIsNone(output)
            self.assertFalse(result.ok)
        self.assertEqual(callback.contexts, [])

    def test_semantic_exception_is_not_masked_as_success(self):
        callback = Mock(side_effect=RuntimeError("domain validator bug"))
        with self.assertRaisesRegex(RuntimeError, "domain validator bug"):
            self.llm_validator.validate('{"value":1}', replace(LEAF_CONTRACT, validator=callback), identity())

    def test_python_semantics_are_delegated_after_ready_pojo_admission(self):
        value = LeafOutput(value=2)
        output, structural = self.contract_validator.validate(value, LeafOutput)
        self.assertTrue(structural.ok)
        result = ValidationResult(status=ValidationStatus.USER_ERROR)
        callback = RecordingValidator[LeafOutput](result)
        ctx = NodeValidationContext(output, identity())
        self.assertIs(self.node_validator.validate(ctx, replace(LEAF_CONTRACT, validator=callback)), result)
        self.assertIs(callback.contexts[0].output, value)

    def test_context_is_frozen_and_counters_reuse_strict_index_constraints(self):
        ctx = NodeValidationContext(LeafOutput(value=1), identity())
        with self.assertRaises(FrozenInstanceError):
            ctx.output = LeafOutput(value=2)
        for field in ("pass_number", "repair_attempt"):
            for value in (-1, True, "1"):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    NodeValidationContext(LeafOutput(value=1), identity(), **{field: value})

    def test_target_validation_imports_do_not_load_production_nodes(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run(
            [sys.executable, "-c", "import sys,json; from app.application.engine.runtime.validation.llmValidator import LLMValidator; print(json.dumps([name for name in sys.modules if name == 'app.application.engine.nodes' or name.startswith('app.application.engine.nodes.')]))"],
            cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "backend")),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
