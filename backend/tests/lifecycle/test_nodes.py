from dataclasses import replace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from pydantic import ValidationError
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.validation.validationStatus import ValidationStatus
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.results.errors import LifecycleFieldError, LifecycleSectionRefused
from tests.lifecycle.support import nodeContracts as c, nodeBindings as b, mixedContracts as m
from tests.lifecycle import test_preparation as preparation, test_section as section


class NodeTests(IsolatedAsyncioTestCase):
    async def test_nine_registered_operations_execute_and_admit_exact_outputs(self):
        registry = NodeRegistry()
        b.register_mock_nodes(registry)
        self.assertEqual(len(registry.ids()), 9)
        for operation in LifecycleOperation:
            for suffix in ("A", "B"):
                name = ("Replace" if operation is LifecycleOperation.REPLACEMENT else operation.value.title())
                contract = getattr(c, (name + suffix).upper() + "_CONTRACT")
                node_type = getattr(b, name + suffix + "Node")
                ready = contract.input_type(request=preparation.request_for(operation, suffix))
                node = node_type(ready_input=ready, pipeline=preparation.PreparationTests().pipeline(operation, suffix))
                registration = registry.get(node.id, contract)
                self.assertIs(registration.executor_cls, PythonNodeExecutor)
                registration.validate_node(node)
                output = await PythonNodeExecutor().execute(node, ready)
                admitted, status = ContractValidator().validate(output, contract.output_type)
                self.assertIs(admitted, output)
                self.assertIs(status.status, ValidationStatus.OK)
                self.assertIs(type(output.value), getattr(m, name + suffix))
                self.assertEqual(contract.error_types, ())
                self.assertEqual(contract.reads, ())
                self.assertEqual(contract.calls, ())
                self.assertEqual(contract.version, "1")
        request = section.mixed_request()
        ready = c.SectionNodeInputAB(request=request)
        node = b.SectionABNode(ready_input=ready,
            pipeline=LifecycleSectionPipelineOpenPipeline(binding=section.section_binding()))
        result = await PythonNodeExecutor().execute(node, ready)
        self.assertIs(type(result.value), m.LifecycleSectionAB)
        self.assertEqual(result.value.domain_evidence, request.domain_evidence)
        self.assertIs(registry.get(node.id, c.SECTIONAB_CONTRACT).node_cls, b.SectionABNode)
        self.assertIs(ContractValidator().validate(result, c.SectionNodeOutputAB)[1].status, ValidationStatus.OK)

    async def test_refusals_are_output_values(self):
        request = preparation.request_for(LifecycleOperation.CREATE, "A")
        request = request.model_copy(update={"capture": request.capture.model_copy(update={"entities": ()})})
        ready = c.CreateNodeInputA(request=request)
        node = b.CreateANode(ready_input=ready, pipeline=preparation.PreparationTests().pipeline(LifecycleOperation.CREATE, "A"))
        result = await PythonNodeExecutor().execute(node, ready)
        self.assertIs(type(result.value), LifecycleFieldError)
        self.assertIs(ContractValidator().validate(result, c.CreateNodeOutputA)[1].status, ValidationStatus.OK)
        request = section.mixed_request().model_copy(update={"domain_evidence": ()})
        ready = c.SectionNodeInputAB(request=request)
        node = b.SectionABNode(ready_input=ready,
            pipeline=LifecycleSectionPipelineOpenPipeline(binding=section.section_binding()))
        result = await PythonNodeExecutor().execute(node, ready)
        self.assertIs(type(result.value), LifecycleSectionRefused)

    async def test_wrong_specialization_and_subclass_cannot_cross_boundary(self):
        request_a = preparation.request_for(LifecycleOperation.CREATE, "A")
        request_b = preparation.request_for(LifecycleOperation.CREATE, "B")
        with self.assertRaises(ValidationError):
            c.CreateNodeInputA(request=request_b)
        class DerivedRequest(m.CreateRequestA):
            pass
        with self.assertRaises(ValidationError):
            c.CreateNodeInputA(request=DerivedRequest(**dict(request_a)))
        result_b = preparation.PreparationTests().pipeline(LifecycleOperation.CREATE, "B").prepare_create(request_b)
        with self.assertRaises(ValidationError):
            c.CreateNodeOutputA(value=result_b)
        fake = Mock()
        node = b.CreateANode(ready_input=c.CreateNodeInputA(request=request_a), pipeline=fake)
        with self.assertRaises(TypeError):
            await node.execute(c.CreateNodeInputB(request=request_b))
        fake.prepare_create.assert_not_called()
        fake.prepare_create.return_value = result_b
        with self.assertRaises(ValidationError):
            await node.execute(node.ready_input)
        malformed = c.CreateNodeOutputA.model_construct(value=result_b)
        self.assertIs(ContractValidator().validate(malformed, c.CreateNodeOutputA)[1].status, ValidationStatus.FAIL)

    def test_registry_rejects_duplicate_id_and_other_contract_identity(self):
        registry = NodeRegistry()
        b.register_mock_nodes(registry)
        with self.assertRaises(ValueError):
            b.register_mock_nodes(registry)
        with self.assertRaises(TypeError):
            registry.get(NodeId("engine.lifecycle.test_a.prepare_create"), c.CREATEB_CONTRACT)
        with self.assertRaises(TypeError):
            registry.get(NodeId("engine.lifecycle.test_a.prepare_create"), replace(c.CREATEA_CONTRACT))
