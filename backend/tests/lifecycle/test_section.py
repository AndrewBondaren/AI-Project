import unittest
from unittest.mock import patch

from app.application.lifecycle.contracts.sectionBinding import LifecycleSectionBinding, LifecyclePatchModelBinding
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.application.lifecycle.publication.sectionBuilder import LifecycleSectionBuilder
from app.application.lifecycle.publication.sectionCodec import LifecycleSectionCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.registry.boundSectionCodec import BoundSectionCodec
from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from app.dataModel.lifecycle.results.issues import LifecycleRelationCode as R
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.encoding.canonicalCodec import content_digest
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support.manifest import MOCK_NATIVE_MANIFEST
from tests.lifecycle import test_preparation as preparation


def section_binding():
    contract = SectionContract(key="mock.lifecycle", section_model=m.LifecycleSectionAB,
                               supported_versions=frozenset({1}), manifest=MOCK_NATIVE_MANIFEST)
    return LifecycleSectionBinding(request_model=m.PrepareLifecycleSectionAB, section_contract=contract,
        patch_bindings=tuple(LifecyclePatchModelBinding(getattr(m, name + suffix), getattr(m, name + "Patch" + suffix))
                             for name in ("Create", "Replace", "End", "Reactivate") for suffix in ("A", "B")))


def prepared_and_coverage(operation, suffix, index):
    request = preparation.request_for(operation, suffix)
    # Independent entity/action/transition identities across the section.
    intent = request.intent
    refs = intent.predecessors + intent.successors if operation is Op.REPLACEMENT else (intent.entity,)
    replacements = {ref: type(ref)(kind=ref.kind, entity_uid=f"{ref.entity_uid}-{index}") for ref in refs}
    observations = tuple(type(fact)(state=fact.state.model_copy(update={"entity": replacements[fact.state.entity]}))
                         if isinstance(fact, (m.PresentA, m.PresentB)) else type(fact)(entity=replacements[fact.entity])
                         for fact in request.capture.entities)
    intent_changes = {"change_uid": f"change-{index}"}
    if operation is Op.REPLACEMENT:
        intent_changes.update(predecessors=tuple(replacements[r] for r in intent.predecessors),
                              successors=tuple(replacements[r] for r in intent.successors))
    else:
        intent_changes["entity"] = replacements[intent.entity]
    effects = tuple(effect.model_copy(update={"entity": replacements[effect.entity]}) for effect in request.admission.effects)
    facts = tuple(fact.model_copy(update={"entity": replacements[fact.entity]}) for fact in request.capture.last_transitions)
    request = request.model_copy(update={
        "intent": intent.model_copy(update=intent_changes),
        "capture": request.capture.model_copy(update={"entities": observations, "last_transitions": facts}),
        "admission": request.admission.model_copy(update={"effects": effects}),
    })
    result = getattr(preparation.PreparationTests().pipeline(operation, suffix), "prepare_" + operation.value)(request)
    dependency = PreparedSectionDependency(section_key="mock.subject." + suffix.lower(), section_fingerprint="b" * 64)
    coverage = tuple(getattr(m, "Coverage" + suffix)(change_uid=request.intent.change_uid, effect=effect,
        section=dependency, patch_refs=(PatchRef(operation_id="publish", section_key=dependency.section_key, ordinal=index),))
        for effect in effects)
    return result, coverage


def mixed_request():
    pairs = [prepared_and_coverage(op, suffix, index)
             for index, (op, suffix) in enumerate((op, suffix) for op in Op for suffix in ("A", "B"))]
    # Deliberately non-transition order: copying evidence must preserve this order.
    evidence = tuple(entry for _, entries in reversed(pairs) for entry in entries)
    return m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=pairs[0][0].base,
        changes=tuple(prepared for prepared, _ in pairs), domain_evidence=evidence)


class SectionTests(unittest.TestCase):
    def test_current_section_evidence_roundtrip_preserves_types_values_and_order(self):
        binding = section_binding()
        request = mixed_request()
        section = LifecycleSectionPipelineOpenPipeline(binding=binding).prepare_section(request)
        self.assertIs(type(section), m.LifecycleSectionAB)
        self.assertEqual(section.domain_evidence, request.domain_evidence)
        self.assertEqual([type(e) for e in section.domain_evidence], [type(e) for e in request.domain_evidence])
        codec = BoundSectionCodec(binding.section_contract, LifecycleSectionCodec(binding.section_contract))
        restored = codec.decode(codec.encode(section), 1)
        self.assertEqual(restored, section)
        self.assertEqual([type(p) for p in restored.patches], [type(p) for p in section.patches])
        self.assertEqual([type(e) for e in restored.domain_evidence], [type(e) for e in section.domain_evidence])
        self.assertEqual([p.header.ref.ordinal for p in restored.patches], list(range(8)))
        self.assertTrue(all(set(type(p).model_fields) == {"header", "prepared"} for p in restored.patches))
        altered = section.model_copy(update={"domain_evidence": tuple(reversed(section.domain_evidence))})
        self.assertNotEqual(content_digest(codec.encode(section)), content_digest(codec.encode(altered)))

    def test_missing_coverage_is_a_value_and_never_calls_builder(self):
        request = mixed_request().model_copy(update={"domain_evidence": ()})
        with patch.object(LifecycleSectionBuilder, "build", side_effect=AssertionError("builder called")):
            result = LifecycleSectionPipelineOpenPipeline(binding=section_binding()).prepare_section(request)
        self.assertIs(type(result), LifecycleSectionRefused)
        self.assertTrue(all(issue.code is R.COVERAGE_MISSING for issue in result.issues))
        self.assertEqual(len(result.issues), 10)

    def test_many_to_many_preserves_shared_patch_refs(self):
        prepared, coverage = prepared_and_coverage(Op.REPLACEMENT, "A", 0)
        refs = (coverage[0].patch_refs[0], coverage[0].patch_refs[0].model_copy(update={"ordinal": 1}))
        coverage = tuple(entry.model_copy(update={"patch_refs": refs}) for entry in coverage)
        request = m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=prepared.base,
            changes=(prepared,), domain_evidence=coverage)
        section = LifecycleSectionPipelineOpenPipeline(binding=section_binding()).prepare_section(request)
        self.assertIs(type(section), m.LifecycleSectionAB)
        self.assertEqual(len(section.patches), 1)
        self.assertTrue(all(entry.patch_refs == refs for entry in section.domain_evidence))

    def test_coverage_relation_failures_aggregate(self):
        request = mixed_request()
        first = request.domain_evidence[0]
        bad_ref = first.patch_refs[0].model_copy(update={"operation_id": "other", "section_key": "other.section"})
        altered = first.model_copy(update={"patch_refs": (bad_ref,),
            "section": first.section.model_copy(update={"section_fingerprint": "c" * 64})})
        request = request.model_copy(update={"domain_evidence": request.domain_evidence + (altered,)})
        result = LifecycleSectionPipelineOpenPipeline(binding=section_binding()).prepare_section(request)
        self.assertIs(type(result), LifecycleSectionRefused)
        codes = [issue.code for issue in result.issues]
        for code in (R.COVERAGE_DUPLICATE, R.PATCH_OPERATION_MISMATCH, R.PATCH_SECTION_MISMATCH, R.FINGERPRINT_CONFLICT):
            self.assertIn(code, codes)

    def test_wrong_wrapper_model_fails_at_construction(self):
        with self.assertRaises(TypeError):
            LifecyclePatchModelBinding(m.CreateA, m.CreatePatchB)

    def test_one_hundred_independent_creates_produce_one_hundred_patches(self):
        pairs = tuple(prepared_and_coverage(Op.CREATE, "A", index) for index in range(100))
        request = m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=pairs[0][0].base,
            changes=tuple(p for p, _ in pairs), domain_evidence=tuple(e for _, coverage in pairs for e in coverage))
        section = LifecycleSectionPipelineOpenPipeline(binding=section_binding()).prepare_section(request)
        self.assertIs(type(section), m.LifecycleSectionAB)
        self.assertEqual(len(section.patches), 100)
        self.assertEqual([p.header.ref.ordinal for p in section.patches], list(range(100)))

    def test_one_replacement_with_one_hundred_participants_is_one_patch(self):
        original = preparation.request_for(Op.REPLACEMENT, "A")
        predecessors = tuple(m.RefA(kind="test_entity_a", entity_uid=f"old-{i}") for i in range(50))
        successors = tuple(m.RefA(kind="test_entity_a", entity_uid=f"new-{i}") for i in range(50))
        before = original.capture.entities[0].state
        observations = tuple(m.PresentA(state=before.model_copy(update={"entity": ref})) for ref in predecessors)
        observations += tuple(m.AbsentA(entity=ref) for ref in successors)
        effects = tuple(m.EffectA(entity=ref, effect="end", reason_action_uid="action") for ref in predecessors)
        effects += tuple(m.EffectA(entity=ref, effect="create", reason_action_uid="action") for ref in successors)
        request = original.model_copy(update={
            "intent": original.intent.model_copy(update={"predecessors": predecessors, "successors": successors}),
            "capture": original.capture.model_copy(update={"entities": observations}),
            "admission": original.admission.model_copy(update={"effects": effects}),
        })
        prepared = preparation.PreparationTests().pipeline(Op.REPLACEMENT, "A").prepare_replacement(request)
        dep = PreparedSectionDependency(section_key="mock.subject.a", section_fingerprint="b" * 64)
        coverage = tuple(m.CoverageA(change_uid="change", effect=effect, section=dep,
            patch_refs=(PatchRef(operation_id="publish", section_key=dep.section_key, ordinal=0),)) for effect in effects)
        section = LifecycleSectionPipelineOpenPipeline(binding=section_binding()).prepare_section(
            m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=prepared.base,
                changes=(prepared,), domain_evidence=coverage))
        self.assertIs(type(section), m.LifecycleSectionAB)
        self.assertEqual(len(section.patches), 1)
        self.assertEqual(len(section.patches[0].prepared.transition.participants), 100)


if __name__ == "__main__":
    unittest.main()
