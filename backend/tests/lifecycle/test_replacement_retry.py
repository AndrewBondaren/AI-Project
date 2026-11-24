from unittest import IsolatedAsyncioTestCase

from app.application.lifecycle.changes.semanticEquality import equivalent_transition
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.application.lifecycle.publication.sectionCodec import LifecycleSectionCodec
from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.encoding.canonicalCodec import content_digest
from tests.lifecycle import test_preparation as preparation, test_section as sections
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support.lifecycleParticipant import MockLifecycleParticipant
from tests.lifecycle.test_participant import MockCommitScope


class ReplacementRetryTests(IsolatedAsyncioTestCase):
    async def test_multilateral_reordering_is_noop_but_preserves_wire_order(self):
        for suffix in ("A", "B"):
            with self.subTest(kind=suffix):
                request = preparation.request_for(Op.REPLACEMENT, suffix)
                ref_model = getattr(m, "Ref" + suffix)
                predecessors = tuple(ref_model(kind=request.intent.predecessors[0].kind,
                    entity_uid=f"old-{i}") for i in range(3))
                successors = tuple(ref_model(kind=predecessors[0].kind, entity_uid=f"new-{i}") for i in range(2))
                state = request.capture.entities[0].state
                observations = tuple(getattr(m, "Present" + suffix)(state=state.model_copy(update={"entity": ref}))
                    for ref in predecessors) + tuple(getattr(m, "Absent" + suffix)(entity=ref) for ref in successors)
                effects = tuple(getattr(m, "Effect" + suffix)(entity=ref, effect=effect, reason_action_uid="action")
                    for refs, effect in ((predecessors, Op.END), (successors, Op.CREATE)) for ref in refs)
                request = request.model_copy(update={
                    "intent": request.intent.model_copy(update={"predecessors": predecessors, "successors": successors}),
                    "capture": request.capture.model_copy(update={"entities": observations}),
                    "admission": request.admission.model_copy(update={"effects": effects})})
                pipeline = preparation.PreparationTests().pipeline(Op.REPLACEMENT, suffix)
                original = pipeline.prepare_replacement(request)
                reordered = pipeline.prepare_replacement(request.model_copy(update={"intent": request.intent.model_copy(
                    update={"predecessors": tuple(reversed(predecessors)), "successors": tuple(reversed(successors))})}))
                self.assertTrue(equivalent_transition(original.transition, reordered.transition))
                self.assertEqual(tuple(p.after.entity for p in reordered.transition.participants),
                                 tuple(reversed(predecessors)) + tuple(reversed(successors)))
                changed = reordered.transition.model_copy(update={"intent": reordered.transition.intent.model_copy(
                    update={"reason": reordered.transition.intent.reason.model_copy(update={"action_uid": "different"})})})
                self.assertFalse(equivalent_transition(original.transition, changed))
                dep = PreparedSectionDependency(section_key="mock.subject." + suffix.lower(), section_fingerprint="b" * 64)
                coverage = tuple(getattr(m, "Coverage" + suffix)(change_uid=request.intent.change_uid, effect=e,
                    section=dep, patch_refs=(PatchRef(operation_id="publish", section_key=dep.section_key, ordinal=0),)) for e in effects)
                binding = sections.section_binding()
                builder = LifecycleSectionPipelineOpenPipeline(binding=binding)
                natives = tuple(builder.prepare_section(m.PrepareLifecycleSectionAB(operation_id="publish",
                    expected_world=p.base, changes=(p,), domain_evidence=coverage)) for p in (original, reordered))
                codec = LifecycleSectionCodec(binding.section_contract)
                self.assertNotEqual(content_digest(codec.encode(natives[0])), content_digest(codec.encode(natives[1])))
                scope = MockCommitScope()
                store = MockLifecycleParticipant(scope=scope, publication=original.base,
                    states=tuple(f.state for f in observations if f.status == "present"))
                target = WorldSnapshotRef(world_uid=original.base.world_uid,
                    timeline_id=original.base.active_timeline_id, snapshot_id="assigned")
                first = await store.append(natives[0], expected=original.base, target=target)
                self.assertEqual(first.changed, (natives[0].patches[0].header.ref,))
                retry = await store.append(natives[1], expected=original.base, target=target)
                self.assertEqual((retry.changed, retry.state, retry.history), ((), None, None))
