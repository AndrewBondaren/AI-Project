"""A3.3: bound prepared Inputs, one group schema and native wire projection."""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Never
import unittest
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId
from tests.dag_typing.fixtures import (
    CompositeOutput, LeafOutput, MutableBoundaryOutput, NodeInput, OtherInput, TypedLLMNode,
)


class Registry:
    def __init__(self):
        self.calls = []
        self.texts = {"llm_group": "Global instructions", "node": "Use {{language}}", "patch": "Repair instruction"}

    def get(self, key):
        self.calls.append(key)
        return self.texts[key]


class NestedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    leaves: tuple[LeafOutput, ...]
    hint: str | None = None


class AliasedInput(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)
    value: int = Field(serialization_alias="wire_value")


class PrivateInput(NodeInput):
    private_detail: str


class ArrayInput(RootModel[tuple[int, ...]]):
    model_config = ConfigDict(frozen=True)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.dsl = Registry()
        self.builder = LLMGroupPayloadBuilder(DSLResolver(self.dsl))
        self.node = TypedLLMNode(id=TypedLLMNode.id, dsl="node")
        self.registry = NodeRegistry()
        self.contract = NodeContract[NodeInput, LeafOutput, Never](
            NodeInput, LeafOutput, ContractId("test.payload"), ContractVersion("1"), (), error_types=(),
        )
        self.registry.register_llm(TypedLLMNode, self.contract)
        self.registration = self.registry.get(self.node.id, self.contract)

    def section(self, value=None, **kwargs):
        return self.builder.section(self.node, self.registration,
                                    NodeInput(value=7) if value is None else value, language="ru", **kwargs)

    def payload(self, *sections):
        return self.builder.build(tuple(sections), player_message="Привет", language="ru")

    def test_prepared_input_is_kept_as_same_immutable_instance_until_wire(self):
        value = NodeInput(value=42)
        with patch.object(NodeInput, "model_dump", side_effect=AssertionError("eager dump")), \
             patch.object(NodeInput, "__deepcopy__", side_effect=AssertionError("payload copy")):
            section = self.section(value)
            payload = self.payload(section)
            self.assertIs(section.input, value)
            self.assertIs(payload.sections[0], section)
        with self.assertRaises(FrozenInstanceError):
            section.input = NodeInput(value=1)
        with self.assertRaises(FrozenInstanceError):
            payload.language = "en"
        self.assertEqual(payload.to_dict()[self.node.id]["context_data"], {"value": 42})

    def test_existing_dsl_global_and_language_substitution_are_reused(self):
        payload = self.payload(self.section(dsl_keys=("node", "patch")))
        self.assertEqual(payload.global_dsl, "Global instructions")
        self.assertEqual(payload.sections[0].dsl, "Use ru\n\nRepair instruction")
        self.assertEqual(self.dsl.calls, ["node", "patch", "llm_group"])

    def test_explicit_empty_dsl_keys_do_not_restore_default(self):
        self.assertEqual(self.section(dsl_keys=()).dsl, "")

    def test_group_schema_uses_each_bound_output_pojo(self):
        section = self.section()
        other = replace(section, node_id=NodeId("other"), output_type=NestedOutput)
        payload = self.payload(section, other)
        schema = payload.response_format_schema
        self.assertEqual(schema["required"], [self.node.id, "other"])
        self.assertFalse(schema["additionalProperties"])
        nested = schema["properties"]["other"]
        self.assertEqual(nested["required"], ["leaves", "hint"])
        self.assertFalse(nested["additionalProperties"])
        self.assertFalse(nested["properties"]["leaves"]["items"]["additionalProperties"])
        self.assertNotIn("default", nested["properties"]["hint"])
        self.assertNotIn("$ref", json.dumps(schema))
        self.assertNotIn("$defs", json.dumps(schema))
        self.assertIn("null", json.dumps(nested["properties"]["hint"]))

    def test_schema_is_one_common_helper_call_for_whole_group(self):
        from app.application.engine.prompt.schemaBuilder import build_strict_schema
        section = self.section()
        payload = self.payload(section, replace(section, node_id=NodeId("other")))
        with patch("app.application.engine.runtime.prompt.pojo.llmPayload.build_strict_schema", wraps=build_strict_schema) as helper:
            wire = payload.to_dict()
        self.assertEqual(helper.call_count, 1)
        self.assertEqual(set(wire["response_format"]["properties"]), {self.node.id, "other"})

    def test_schema_wire_mutation_does_not_mutate_future_projection_or_output_schema(self):
        payload = self.payload(self.section())
        first = payload.to_dict()
        first["response_format"]["properties"].clear()
        self.assertEqual(set(payload.response_format_schema["properties"]), {self.node.id})
        self.assertIn("value", LeafOutput.model_json_schema()["properties"])

    def test_declared_input_type_controls_subclass_serialization(self):
        value = PrivateInput(value=3, private_detail="secret")
        section = self.section(value)
        self.assertIs(section.input, value)
        self.assertEqual(self.payload(section).to_dict()[self.node.id]["context_data"], {"value": 3})

    def test_native_alias_and_root_input_serialization(self):
        for model, value, expected in (
            (AliasedInput, AliasedInput(value=4), {"wire_value": 4}),
            (ArrayInput, ArrayInput((1, 2)), [1, 2]),
        ):
            with self.subTest(model=model):
                section = replace(self.section(), input_type=model, input=value)
                self.assertEqual(self.payload(section).to_dict()[self.node.id]["context_data"], expected)

    def test_wire_shapes_support_system_role_and_single_user_message(self):
        payload = self.payload(self.section())
        full, user = payload.to_dict(), payload.to_user_dict()
        self.assertEqual(full.pop("dsl"), payload.global_dsl)
        self.assertEqual(full, user)
        self.assertEqual(json.loads(json.dumps(user, ensure_ascii=False)), user)
        self.assertEqual(user["player_message"], "Привет")
        self.assertEqual(user["language"], "ru")

    def test_raw_wrong_mutable_and_forged_inputs_are_rejected(self):
        for value in ({"value": 1}, OtherInput(text="wrong"), MutableBoundaryOutput(value=1), NodeInput.model_construct(value="bad")):
            with self.subTest(value=value), self.assertRaisesRegex(TypeError, "Input"):
                self.section(value)

    def test_wrong_node_or_kind_cannot_supply_binding(self):
        with self.assertRaisesRegex(TypeError, "binding"):
            self.builder.section(replace(self.node, id=NodeId("other")), self.registration, NodeInput(value=1), language="ru")
        with self.assertRaisesRegex(TypeError, "LLM binding"):
            self.builder.section(self.node, replace(self.registration, kind=NodeKind.PYTHON), NodeInput(value=1), language="ru")

    def test_empty_duplicate_and_reserved_group_nodes_are_rejected(self):
        section = self.section()
        for sections in ((), (section, section), (replace(section, node_id=NodeId("language")),)):
            with self.subTest(sections=sections), self.assertRaises(ValueError):
                self.payload(*sections)

    def test_mutable_sections_or_dsl_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            self.builder.build([self.section()], player_message="", language="ru")
        for keys in (["node"], (1,)):
            with self.subTest(keys=keys), self.assertRaises(TypeError):
                self.section(dsl_keys=keys)

    def test_heterogeneous_sections_keep_distinct_input_schemas_and_payloads(self):
        first = self.section()
        second = replace(first, node_id=NodeId("second"), input_type=OtherInput,
                         input=OtherInput(text="different"), output_type=CompositeOutput)
        payload = self.payload(first, second)
        self.assertIs(payload.sections[1].input, second.input)
        wire = payload.to_dict()
        self.assertEqual(wire["second"]["context_data"], {"text": "different"})
        self.assertIn("leaves", wire["response_format"]["properties"]["second"]["properties"])

    def test_target_import_has_no_legacy_nodes_or_runtime_wiring(self):
        root = Path(__file__).resolve().parents[4]
        code = """
import sys
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
assert not any(k.startswith('app.application.engine.nodes') for k in sys.modules)
assert 'app.application.engine.prompt.llmGroupPayloadBuilder' not in sys.modules
assert 'app.core.container.engine' not in sys.modules
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=root, env={**os.environ, "PYTHONPATH": str(root / "backend")}, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
