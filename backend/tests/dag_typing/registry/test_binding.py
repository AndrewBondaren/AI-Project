"""A1.2: typed bindings, request-local construction and import boundaries."""

from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from pydantic import BaseModel, ValidationError

from app.application.engine.contracts.executionBindings import ResolveResult
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.registration.nodeRegistry import NodeRegistry, register_llm, register_python
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from tests.dag_typing.fixtures import (
    CompositeOutput, FakeExecutor, FakeReadView, LEAF_CONTRACT, LeafOutput, NodeInput,
    OPTIONAL_COMPOSITE, REQUIRED_LEAF, TypedLLMNode, TypedPythonNode,
)


class BindingTests(unittest.TestCase):
    def test_python_phase_accepts_only_enum_members_of_python_subset(self):
        self.assertIs(TypedPythonNode(request_value=1).phase, ExecutionPhase.PRE_LLM)
        for phase in (ExecutionPhase.PRE_LLM, ExecutionPhase.POST_LLM):
            with self.subTest(phase=phase):
                self.assertIs(TypedPythonNode(request_value=1, phase=phase).phase, phase)
        for phase in ("pre_llm", "post_llm", "llm", "arbitrary", ExecutionPhase.LLM, None, 1):
            with self.subTest(phase=phase), self.assertRaises((TypeError, ValidationError)):
                TypedPythonNode(request_value=1, phase=phase)

    def test_registration_never_constructs_node_and_preserves_contract(self):
        # Construction needs request_value, unavailable at registration time.
        registry = NodeRegistry()
        self.assertIs(registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT), TypedPythonNode)
        registration = registry.get(NodeId("typed-python"), LEAF_CONTRACT)
        self.assertIs(registration.node_cls, TypedPythonNode)
        self.assertIs(registration.executor_cls, FakeExecutor)
        self.assertIs(registration.contract, LEAF_CONTRACT)
        self.assertIs(registration.contract.input_type, NodeInput)
        self.assertIs(registration.contract.output_type, LeafOutput)
        self.assertEqual(registration.kind, NodeKind.PYTHON)

    def test_llm_uses_output_pojo_without_legacy_schema_or_validator(self):
        registry = NodeRegistry()
        self.assertIs(registry.register_llm(TypedLLMNode, LEAF_CONTRACT), TypedLLMNode)
        registration = registry.get(NodeId("typed-llm"), LEAF_CONTRACT)
        self.assertIsNone(registration.executor_cls)
        self.assertEqual(registration.kind, NodeKind.LLM)
        self.assertFalse(hasattr(TypedLLMNode(), "contract_json"))
        self.assertIs(registration.contract.output_type, LeafOutput)

    def test_decorators_delegate_to_explicit_registry(self):
        registry = NodeRegistry()
        self.assertIs(register_python(FakeExecutor, LEAF_CONTRACT, registry=registry)(TypedPythonNode), TypedPythonNode)
        self.assertIs(register_llm(LEAF_CONTRACT, registry=registry)(TypedLLMNode), TypedLLMNode)
        self.assertEqual(set(registry.ids()), {"typed-python", "typed-llm"})
        self.assertEqual(NodeRegistry().ids(), ())

    def test_duplicate_ids_are_rejected_even_with_different_contract(self):
        registry = NodeRegistry()
        registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
        for contract in (LEAF_CONTRACT, replace(LEAF_CONTRACT, version=ContractVersion("2"))):
            with self.assertRaisesRegex(ValueError, "already registered"):
                registry.register_python(TypedPythonNode, FakeExecutor, contract)
        self.assertIs(registry.get(NodeId("typed-python"), LEAF_CONTRACT).contract, LEAF_CONTRACT)

    def test_typed_lookup_requires_the_registered_contract(self):
        registry = NodeRegistry()
        registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
        incompatible = NodeContract(NodeInput, CompositeOutput, ContractId("test.leaf"), ContractVersion("1"), ())
        with self.assertRaisesRegex(TypeError, "contract does not match"):
            registry.get(NodeId("typed-python"), incompatible)
        with self.assertRaises(KeyError):
            registry.get(NodeId("missing"), LEAF_CONTRACT)

    def test_contract_and_reads_are_mandatory(self):
        registry = NodeRegistry()
        with self.assertRaises(TypeError):
            registry.register_python(TypedPythonNode, FakeExecutor)
        with self.assertRaises(TypeError):
            registry.register_llm(TypedLLMNode)
        with self.assertRaises(TypeError):
            registry.register_python(TypedPythonNode, FakeExecutor, None)
        with self.assertRaises(TypeError):
            NodeContract(NodeInput, LeafOutput, ContractId("test"), ContractVersion("1"))

    def test_invalid_pojo_classes_and_declarations_are_rejected(self):
        for model in (str, LeafOutput(value=1), None):
            with self.subTest(model=model):
                with self.assertRaises((TypeError, ValidationError)):
                    NodeContract(model, LeafOutput, ContractId("test"), ContractVersion("1"), ())
                with self.assertRaises((TypeError, ValidationError)):
                    NodeContract(NodeInput, model, ContractId("test"), ContractVersion("1"), ())
                with self.assertRaises((TypeError, ValidationError)):
                    OutputRef(NodeId("producer"), model)
        for declarations in ([REQUIRED_LEAF], (object(),)):
            with self.assertRaises(TypeError):
                replace(LEAF_CONTRACT, reads=declarations)
        for declaration in (RequiredOutput, OptionalOutput):
            with self.assertRaises(TypeError):
                declaration(object())

    def test_identifier_validation_reuses_existing_id_constraints(self):
        for value in ("", " bad", "bad ", 1):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    OutputRef(value, LeafOutput)
                with self.assertRaises(ValidationError):
                    replace(LEAF_CONTRACT, contract_id=value)
                with self.assertRaises(ValidationError):
                    replace(LEAF_CONTRACT, version=value)

    def test_wrong_node_kind_or_executor_is_rejected_without_construction(self):
        registry = NodeRegistry()
        with self.assertRaises(TypeError):
            registry.register_python(TypedLLMNode, FakeExecutor, LEAF_CONTRACT)
        with self.assertRaises(TypeError):
            registry.register_llm(TypedPythonNode, LEAF_CONTRACT)
        for executor in (None, object, FakeExecutor()):
            with self.assertRaises(TypeError):
                registry.register_python(TypedPythonNode, executor, LEAF_CONTRACT)
        self.assertEqual(registry.ids(), ())

    def test_registration_requires_static_node_id(self):
        class MissingId(TypedPythonNode):
            id = ""

        with self.assertRaises(ValidationError):
            NodeRegistry().register_python(MissingId, FakeExecutor, LEAF_CONTRACT)

    def test_factory_admission_and_request_isolation(self):
        registry = NodeRegistry()
        registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
        registration = registry.get(NodeId("typed-python"), LEAF_CONTRACT)
        first = TypedPythonNode(request_value=1)
        second = TypedPythonNode(request_value=2)
        registration.validate_node(first)
        registration.validate_node(second)
        self.assertNotEqual(first.request_value, second.request_value)
        with self.assertRaises(TypeError):
            registration.validate_node(TypedLLMNode())
        with self.assertRaises(TypeError):
            registration.validate_node(replace(first, id=NodeId("different")))
        self.assertIs(registration.contract, LEAF_CONTRACT)

    def test_declarations_and_registration_are_frozen(self):
        registry = NodeRegistry()
        registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
        declarations = (
            (LEAF_CONTRACT, "output_type", CompositeOutput),
            (REQUIRED_LEAF, "ref", OPTIONAL_COMPOSITE.ref),
            (OPTIONAL_COMPOSITE.ref, "producer", NodeId("changed")),
            (registry.get(NodeId("typed-python"), LEAF_CONTRACT), "kind", NodeKind.LLM),
        )
        for value, name, replacement in declarations:
            with self.assertRaises(FrozenInstanceError):
                setattr(value, name, replacement)
        self.assertIs(LEAF_CONTRACT.reads[0], REQUIRED_LEAF)
        self.assertIs(LEAF_CONTRACT.reads[1], OPTIONAL_COMPOSITE)

    def subprocess_json(self, source):
        root = Path(__file__).resolve().parents[4]
        env = dict(os.environ, PYTHONPATH=str(root / "backend"))
        result = subprocess.run(
            [sys.executable, "-c", source], cwd=root, env=env,
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_target_imports_do_not_load_production_package(self):
        loaded = self.subprocess_json("""
import importlib, json, sys
for name in (
    'contracts.outputRef', 'contracts.nodeContract', 'contracts.executionBindings',
    'contracts.dagReadView', 'contracts.pythonExecutor',
    'registration.nodeRegistration', 'registration.nodeRegistry',
    'nodeTypes.baseNode', 'nodeTypes.pythonNode', 'nodeTypes.llmNode', 'nodeTypes.compiledNode',
    'nodeTypes.support.nodeKind', 'nodeTypes.support.nodeCost', 'nodeTypes.support.pythonNodeError',
):
    importlib.import_module('app.application.engine.' + name)
print(json.dumps([name for name in sys.modules if name == 'app.application.engine.nodes' or name.startswith('app.application.engine.nodes.')]))
""")
        self.assertEqual(loaded, [])

    def test_production_bootstrap_preserves_baseline_registration_ids(self):
        ids = self.subprocess_json("""
import json
import app.application.engine.nodes
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY
print(json.dumps(sorted(NODE_REGISTRY.all())))
""")
        # Captured from the unchanged production bootstrap before M33 moves.
        self.assertEqual(ids, [
            "check_scene", "check_terrain", "context_snap_gatherer", "eager_terrain",
            "generate_climate", "intent_detection", "lazy_settlement", "lazy_terrain",
            "recalculate_climate", "resolve_weather", "scene_init", "scene_location_children",
            "scene_start_location_select", "terrain_context", "terrain_summary",
        ])


class TypedCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_execute_and_response_use_direct_pojo(self):
        node = TypedPythonNode(request_value=4)
        input_value = await node.prepare_input(FakeReadView(LeafOutput(value=3)))
        self.assertIsInstance(input_value, NodeInput)
        output = await FakeExecutor().execute(node, input_value)
        self.assertEqual(output.value, 7)
        self.assertIsInstance(output, BaseModel)
        response = ResolveResult(ok=True, data=output)
        self.assertIs(response.data, output)
        self.assertIsNone(response.error)
