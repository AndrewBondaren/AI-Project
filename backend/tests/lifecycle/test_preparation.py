import unittest
from unittest.mock import patch

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.application.lifecycle.contracts.preparationPolicy import LifecyclePreparationPolicy, LifecycleReasonDeclaration
from app.application.lifecycle.changes.createPipelineOpenPipeline import LifecycleCreatePipelineOpenPipeline
from app.application.lifecycle.changes.replacementPipelineOpenPipeline import LifecycleReplacementPipelineOpenPipeline
from app.application.lifecycle.changes.endPipelineOpenPipeline import LifecycleEndPipelineOpenPipeline
from app.application.lifecycle.changes.reactivatePipelineOpenPipeline import LifecycleReactivatePipelineOpenPipeline
from app.application.lifecycle.changes.changeBuilder import LifecycleChangeBuilder
from app.application.lifecycle.changes.semanticEquality import equivalent_transition
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.dataModel.lifecycle.results.errors import LifecycleFieldError, LifecycleLogicError
from app.dataModel.lifecycle.results.issues import LifecycleFieldCode as F, LifecycleRelationCode as R
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support.mockWorld import mock_lifecycle_world


def policy():
    return LifecyclePreparationPolicy(reasons=(
        LifecycleReasonDeclaration("test_a_action", m.TestAReason, "test_entity_a", "mock-subject-a"),
        LifecycleReasonDeclaration("test_b_action", m.TestBReason, "test_entity_b", "mock-subject-b"),
    ), reactivation_after=frozenset({Op.END}))


def request_for(operation, suffix):
    base = mock_lifecycle_world()
    name = "Replace" if operation is Op.REPLACEMENT else operation.value.title()
    ref_type = getattr(m, "Ref" + suffix)
    ref = ref_type(kind="test_entity_" + suffix.lower(), entity_uid="one")
    successor = ref_type(kind=ref.kind, entity_uid="two")
    reason = getattr(m, "Test" + suffix + "Reason")(
        reason_id="test_" + suffix.lower() + "_action", action_uid="action", operation=operation)
    last = LifecycleTransitionRef(world_uid=base.world_uid, origin_timeline_id=base.active_timeline_id, change_uid="prior")
    state = getattr(m, "EntityState" + suffix)(entity=ref, active=operation is not Op.REACTIVATE, last_transition=last)
    absent = getattr(m, "Absent" + suffix)
    present = getattr(m, "Present" + suffix)
    fact = getattr(m, "LastTransitionFact" + suffix)(ref=last, operation=Op.END, entity=ref)
    effects = getattr(m, "Effect" + suffix)
    if operation is Op.REPLACEMENT:
        intent = getattr(m, name + "Intent" + suffix)(change_uid="change", reason=reason, predecessors=(ref,), successors=(successor,))
        observations = (present(state=state), absent(entity=successor))
        changes = (effects(entity=ref, effect="end", reason_action_uid="action"), effects(entity=successor, effect="create", reason_action_uid="action"))
    else:
        intent = getattr(m, name + "Intent" + suffix)(change_uid="change", reason=reason, entity=ref)
        observations = (absent(entity=ref) if operation is Op.CREATE else present(state=state),)
        changes = (effects(entity=ref, effect=operation.value, reason_action_uid="action"),)
    return getattr(m, name + "Request" + suffix)(intent=intent,
        capture=getattr(m, "Capture" + suffix)(publication=base, entities=observations,
            last_transitions=(fact,) if operation is Op.REACTIVATE else ()),
        admission=getattr(m, "Admission" + suffix)(publication=base, action_uid="action", effects=changes))


class PreparationTests(unittest.TestCase):
    def pipeline(self, operation, suffix):
        name = "Replace" if operation is Op.REPLACEMENT else operation.value.title()
        target = {Op.CREATE: LifecycleCreatePipelineOpenPipeline, Op.REPLACEMENT: LifecycleReplacementPipelineOpenPipeline,
                  Op.END: LifecycleEndPipelineOpenPipeline, Op.REACTIVATE: LifecycleReactivatePipelineOpenPipeline}[operation]
        return target(binding=LifecyclePreparationBinding(getattr(m, name + "Request" + suffix),
                      getattr(m, name + suffix)), policy=policy())

    def test_all_eight_operations_preserve_types_reason_and_input(self):
        for operation in Op:
            for suffix in ("A", "B"):
                with self.subTest(operation=operation, suffix=suffix):
                    request = request_for(operation, suffix)
                    original = request.model_dump()
                    result = getattr(self.pipeline(operation, suffix), "prepare_" + operation.value)(request)
                    name = "Replace" if operation is Op.REPLACEMENT else operation.value.title()
                    self.assertIs(type(result), getattr(m, name + suffix))
                    self.assertEqual(result.transition.intent.reason, request.intent.reason)
                    self.assertEqual(request.model_dump(), original)
                    self.assertNotIn("header", type(result).model_fields)
                    self.assertEqual(result.transition.participants[-1].after.active, operation is not Op.END)

    def test_independent_errors_aggregate_and_builder_is_not_called(self):
        request = request_for(Op.REACTIVATE, "A")
        bad_base = request.capture.publication.model_copy(update={"publication_id": "other"})
        request = request.model_copy(update={
            "capture": request.capture.model_copy(update={"entities": (), "last_transitions": ()}),
            "admission": request.admission.model_copy(update={"publication": bad_base, "action_uid": "wrong"}),
        })
        with patch.object(LifecycleChangeBuilder, "build_reactivate", side_effect=AssertionError("builder called")):
            result = self.pipeline(Op.REACTIVATE, "A").prepare_reactivate(request)
        self.assertIs(type(result), LifecycleFieldError)
        self.assertEqual([issue.code for issue in result.issues], [R.BASE_MISMATCH, F.REQUIRED_FACT_MISSING, R.ADMISSION_MISMATCH])
        self.assertEqual([issue.path.projection() for issue in result.issues], [("admission",), ("capture", "entities"), ("admission",)])

    def test_reactivation_after_replacement_is_refused(self):
        request = request_for(Op.REACTIVATE, "B")
        fact = request.capture.last_transitions[0].model_copy(update={"operation": Op.REPLACEMENT})
        request = request.model_copy(update={"capture": request.capture.model_copy(update={"last_transitions": (fact,)})})
        result = self.pipeline(Op.REACTIVATE, "B").prepare_reactivate(request)
        self.assertIs(type(result), LifecycleFieldError)
        self.assertEqual(result.issues[0].code, F.REACTIVATION_RULE_UNSUPPORTED)

    def test_duplicate_capture_is_not_silently_overwritten(self):
        request = request_for(Op.CREATE, "A")
        request = request.model_copy(update={"capture": request.capture.model_copy(update={"entities": request.capture.entities * 2})})
        result = self.pipeline(Op.CREATE, "A").prepare_create(request)
        self.assertIs(type(result), LifecycleLogicError)
        self.assertEqual(result.issues[0].code, R.DUPLICATE_PARTICIPANT)

    def test_retry_equality_keeps_reason_and_rejects_duplicate_participants(self):
        request = request_for(Op.REPLACEMENT, "A")
        prepared = self.pipeline(Op.REPLACEMENT, "A").prepare_replacement(request)
        transition = prepared.transition
        self.assertTrue(equivalent_transition(transition, transition))
        changed_reason = transition.intent.reason.model_copy(update={"action_uid": "other-action"})
        changed = transition.model_copy(update={"intent": transition.intent.model_copy(update={"reason": changed_reason})})
        self.assertFalse(equivalent_transition(transition, changed))
        duplicate = transition.model_copy(update={"participants": transition.participants * 2})
        self.assertFalse(equivalent_transition(duplicate, duplicate))


if __name__ == "__main__":
    unittest.main()
