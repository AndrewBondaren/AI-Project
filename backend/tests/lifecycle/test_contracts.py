import unittest
from dataclasses import FrozenInstanceError

from pydantic import ValidationError

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.reads.facts import UnknownFactCause
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support.mockWorld import mock_lifecycle_world


class LifecycleContractsTests(unittest.TestCase):
    def test_all_eight_bindings_close_the_same_named_chain(self):
        for operation in ("Create", "Replace", "End", "Reactivate"):
            for suffix in ("A", "B"):
                with self.subTest(operation=operation, suffix=suffix):
                    request = getattr(m, operation + "Request" + suffix)
                    prepared = getattr(m, operation + suffix)
                    binding = LifecyclePreparationBinding(request, prepared)
                    self.assertIs(binding.intent_model, getattr(m, operation + "Intent" + suffix))
                    self.assertIs(binding.participant_model, getattr(m, "Participant" + suffix))
                    self.assertIs(binding.state_model, getattr(m, "EntityState" + suffix))
                    self.assertIs(binding.ref_model, getattr(m, "Ref" + suffix))

    def test_wrong_kind_and_wrong_operation_cannot_bind(self):
        for prepared in (m.CreateB, m.EndA, m.ReplaceA, m.ReactivateA):
            with self.subTest(prepared=prepared.__name__), self.assertRaises(TypeError):
                LifecyclePreparationBinding(m.CreateRequestA, prepared)

    def test_binding_is_immutable(self):
        binding = LifecyclePreparationBinding(m.CreateRequestA, m.CreateA)
        with self.assertRaises(FrozenInstanceError):
            binding.prepared_model = m.CreateB

    def test_wrong_named_request_and_subclass_are_rejected(self):
        class DerivedRequest(m.CreateRequestA):
            pass

        binding = LifecyclePreparationBinding(m.CreateRequestA, m.CreateA)
        for request in (m.CreateRequestB.model_construct(), DerivedRequest.model_construct()):
            with self.assertRaises(TypeError):
                binding.admit(request)

    def test_b_ref_and_b_reason_cannot_enter_a_intent(self):
        ref_a = m.RefA(kind="test_entity_a", entity_uid="one")
        ref_b = m.RefB(kind="test_entity_b", entity_uid="one")
        reason_a = m.TestAReason(reason_id="test_a_action", action_uid="action", operation=LifecycleOperation.CREATE)
        reason_b = m.TestBReason(reason_id="test_b_action", action_uid="action", operation=LifecycleOperation.CREATE)
        for ref, reason in ((ref_b, reason_a), (ref_a, reason_b)):
            with self.assertRaises(ValidationError):
                m.CreateIntentA(entity=ref, reason=reason, change_uid="change")

    def test_capture_does_not_turn_unknown_into_absence(self):
        ref = m.RefA(kind="test_entity_a", entity_uid="one")
        fact = m.UnknownA(entity=ref, cause=UnknownFactCause.NOT_CAPTURED)
        capture = m.CaptureA(publication=mock_lifecycle_world(), entities=(fact,), last_transitions=())
        self.assertIs(type(capture.entities[0]), m.UnknownA)
        with self.assertRaises(ValidationError):
            m.ParticipantA(before=fact, after=m.EntityStateA.model_construct())

    def test_unchecked_nested_instance_is_revalidated(self):
        ref = m.RefA.model_construct(kind="test_entity_b", entity_uid="one")
        with self.assertRaises(ValidationError):
            m.CreateIntentA(
                entity=ref, change_uid="change",
                reason=m.TestAReason(reason_id="test_a_action", action_uid="action", operation=LifecycleOperation.CREATE),
            )

    def test_replacement_requires_nonempty_typed_sides_and_reason(self):
        ref = m.RefA(kind="test_entity_a", entity_uid="one")
        reason = m.TestAReason(reason_id="test_a_action", action_uid="action", operation=LifecycleOperation.REPLACEMENT)
        for fields in (
            dict(predecessors=(), successors=(ref,), reason=reason),
            dict(predecessors=(ref,), successors=(), reason=reason),
            dict(predecessors=(ref,), successors=(ref,)),
        ):
            with self.assertRaises(ValidationError):
                m.ReplaceIntentA(change_uid="change", **fields)


if __name__ == "__main__":
    unittest.main()
