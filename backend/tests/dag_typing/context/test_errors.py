"""A2.3R: typed error catalog, POJO admission and attempt ownership."""

from dataclasses import replace
import gc
import unittest
import weakref

from pydantic import ConfigDict, ValidationError

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.execution.nodeOutcome import GateSignal
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import ExecutionId, NodeId, PlanRevision
from tests.dag_typing.fixtures import (
    ERROR_CONTRACT, LeafOutput, NodeInput, TestNodeError, TestOtherError, TypedErrorNode,
)


class ErrorCatalogTests(unittest.TestCase):
    def setUp(self):
        self.registry = NodeRegistry()
        self.registry.register_python(TypedErrorNode, PythonNodeExecutor, ERROR_CONTRACT)
        self.catalog = DAGContext(ExecutionId("execution-1"), self.registry)

    def begin(self):
        return self.catalog.begin_attempt(NodeId("typed-error"), PlanRevision("plan-1"))

    def test_error_pojo_is_strict_frozen_and_has_no_application_policy(self):
        for data in ({"item_id": "1"}, {"item_id": -1}, {"item_id": 1, "requires_replan": True}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                TestNodeError(**data)
        error = TestNodeError(item_id=1)
        with self.assertRaises(ValidationError):
            error.item_id = 2
        for name in ("code", "requires_replan", "next_task_type", "replan_reason"):
            self.assertFalse(hasattr(error, name))

    def test_transport_keeps_concrete_pojo_without_putting_payload_in_exception_args(self):
        error = TestOtherError(description="PRIVATE_VALUE")
        transport = PythonNodeError(error)
        self.assertIs(transport.error, error)
        self.assertEqual(transport.args, ("TestOtherError",))
        self.assertNotIn("PRIVATE_VALUE", str(transport))

    def test_close_error_preserves_concrete_type_payload_and_attempt_identity(self):
        for error in (TestNodeError(item_id=1), TestOtherError(description="message")):
            with self.subTest(error=type(error)):
                identity = self.begin()
                self.catalog.close_error(identity, error, ERROR_CONTRACT)
                self.assertIs(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT), error)
                self.assertEqual(self.catalog.closed_attempts[-1], identity)
                self.assertEqual(self.catalog.current_outputs, ())

    def test_new_attempt_removes_previous_error_even_when_next_attempt_fails(self):
        first = self.begin()
        self.catalog.close_error(first, TestNodeError(item_id=1), ERROR_CONTRACT)
        second = self.begin()
        self.assertIsNone(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT))
        self.catalog.close_attempt(second)
        self.assertIsNone(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT))

    def test_duplicate_late_foreign_or_wrong_plan_error_commit_is_rejected(self):
        identity = self.begin()
        error = TestNodeError(item_id=1)
        for forged in (
            identity.model_copy(update={"execution_id": ExecutionId("foreign")}),
            identity.model_copy(update={"plan_revision": PlanRevision("wrong")}),
            identity.model_copy(update={"attempt": 4}),
        ):
            with self.assertRaises((ValueError, RuntimeError)):
                self.catalog.close_error(forged, error, ERROR_CONTRACT)
        self.catalog.close_error(identity, error, ERROR_CONTRACT)
        with self.assertRaises(RuntimeError):
            self.catalog.close_error(identity, error, ERROR_CONTRACT)
        self.begin()
        with self.assertRaises(RuntimeError):
            self.catalog.close_error(identity, error, ERROR_CONTRACT)
        self.assertIsNone(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT))

    def test_equal_but_unregistered_binding_is_rejected_on_read_and_commit(self):
        identity = self.begin()
        other = replace(ERROR_CONTRACT)
        with self.assertRaises(TypeError):
            self.catalog.node_error(NodeId("typed-error"), other)
        with self.assertRaises(TypeError):
            self.catalog.close_error(identity, TestNodeError(item_id=1), other)
        self.catalog.close_error(identity, TestNodeError(item_id=2), ERROR_CONTRACT)

    def test_unknown_error_producer_is_not_optional_absence(self):
        with self.assertRaises(KeyError):
            self.catalog.node_error(NodeId("unknown"), ERROR_CONTRACT)

    def test_rejected_error_payload_does_not_close_or_poison_attempt(self):
        identity = self.begin()
        for error in (LeafOutput(value=1), {"item_id": 1}, TestNodeError.model_construct(item_id="bad")):
            with self.subTest(error=error), self.assertRaises(TypeError):
                self.catalog.close_error(identity, error, ERROR_CONTRACT)
            self.assertIsNone(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT))
        good = TestNodeError(item_id=3)
        self.catalog.close_error(identity, good, ERROR_CONTRACT)
        self.assertIs(self.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT), good)

    def test_mutable_error_or_nested_mutable_payload_is_rejected_by_boundary(self):
        class MutableError(NodeError):
            model_config = ConfigDict(frozen=False)
            item_id: int
        class NestedMutableError(NodeError):
            values: list[int]
        validator = ContractValidator()
        for error in (MutableError.model_construct(item_id=1), NestedMutableError.model_construct(values=[1])):
            admitted, validation = validator.validate_error(error, (type(error),))
            self.assertIsNone(admitted)
            self.assertFalse(validation.ok)

    def test_empty_error_set_never_admits_and_other_union_member_is_undeclared(self):
        validator = ContractValidator()
        for value, types in ((TestNodeError(item_id=1), ()), (TestOtherError(description="x"), (TestNodeError,))):
            admitted, validation = validator.validate_error(value, types)
            self.assertIsNone(admitted)
            self.assertFalse(validation.ok)

    def test_history_does_not_retain_error_payload_after_begin(self):
        error = TestNodeError(item_id=1)
        reference = weakref.ref(error)
        identity = self.begin()
        self.catalog.close_error(identity, error, ERROR_CONTRACT)
        del error
        self.begin()
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(self.catalog.closed_attempts, (identity,))

    def test_contract_requires_concrete_classes_immutable_tuple_and_declared_policy(self):
        for types in ([TestNodeError], (NodeError,), (LeafOutput,), ("TestNodeError",)):
            with self.subTest(types=types), self.assertRaises(TypeError):
                replace(ERROR_CONTRACT, error_types=types)
        with self.assertRaises(TypeError):
            replace(ERROR_CONTRACT, error_types=(), error_policy=lambda error: None)
        with self.assertRaises(TypeError):
            NodeContract(NodeInput, LeafOutput, ERROR_CONTRACT.contract_id, ERROR_CONTRACT.version, ())

    def test_gate_has_typed_target_and_explanatory_reason_without_machine_code(self):
        gate = GateSignal(TaskType.SCENE_INIT, "explanation")
        self.assertFalse(hasattr(gate, "code"))
        for target, reason in (("scene_init", None), (TaskType.SCENE_INIT, 42)):
            with self.assertRaises(ValidationError):
                GateSignal(target, reason)
