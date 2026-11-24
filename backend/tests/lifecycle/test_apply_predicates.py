import unittest

from app.application.lifecycle.validation.stateValidator import LifecycleStateValidator
from app.application.lifecycle.changes.semanticEquality import equivalent_transition
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangeAbsent
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyCode
from app.dataModel.patch.results.sectionResult import SectionAccepted
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support import domainSections as d
from tests.lifecycle.support.acceptedContracts import AcceptedChangeFoundAB, AcceptedChangesResultAB
from tests.lifecycle.support.snapshotContracts import MockLifecycleSectionRefused, MockSubjectSectionRefused
from tests.lifecycle.support.subjectMock import MockSubjectPayloadVerifierA, MockSubjectPayloadVerifierB
from tests.lifecycle.support.evidenceBinding import MockLifecycleEvidenceValidator
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from tests.lifecycle import test_section as sections
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline


def native_and_reads(found=()):
    request = sections.mixed_request()
    native = LifecycleSectionPipelineOpenPipeline(binding=sections.section_binding()).prepare_section(request)
    captures = []
    for suffix in ("A", "B"):
        entries = tuple(p.before for patch in native.patches for p in patch.prepared.transition.participants
                        if type(p) is getattr(m, "Participant" + suffix))
        facts = tuple(getattr(m, "LastTransitionFact" + suffix)(entity=f.state.entity,
            ref=f.state.last_transition, operation=LifecycleOperation.END)
            for f in entries if f.status == "present" and not f.state.active)
        captures.append(getattr(m, "Capture" + suffix)(publication=request.expected_world, entities=entries, last_transitions=facts))
    lookup = AcceptedChangesResultAB(publication=request.expected_world, entries=tuple(
        AcceptedChangeFoundAB(ref=patch.prepared.transition.participants[0].after.last_transition,
                             transition=patch.prepared.transition)
        if index in found else
        AcceptedChangeAbsent(ref=patch.prepared.transition.participants[0].after.last_transition)
        for index, patch in enumerate(native.patches)))
    return native, lookup, tuple(captures), request.expected_world


def subject_section(suffix="A"):
    entity_type = getattr(m, "Ref" + suffix)
    entities = tuple(entity_type(kind="test_entity_" + suffix.lower(), entity_uid=name) for name in ("one", "two"))
    base = sections.mixed_request().expected_world
    effects = tuple(getattr(m, "Effect" + suffix)(entity=entity, effect=LifecycleOperation.CREATE, reason_action_uid="action") for entity in entities)
    patches = tuple(getattr(d, "TestDomainPatch" + suffix)(
        header=PatchHeader(ref=PatchRef(operation_id="publish", section_key="mock.subject." + suffix.lower(), ordinal=i),
                           format_version=2, depends_on=(), artifacts=()), base=base,
        mutations=tuple(getattr(d, "MockMutation" + suffix)(entity=entity, slot=slot, before=None, after=True, action_uid="action")
                        for entity in entities), effects=effects)
        for i, slot in enumerate(("primary", "index")))
    return getattr(d, "TestDomainSection" + suffix)(
        header=SectionHeader(key="mock.subject." + suffix.lower(), format_version=2, depends_on=()), patches=patches)


class ApplyPredicateTests(unittest.TestCase):
    def test_foreign_world_before_and_current_are_rejected(self):
        validator = LifecycleStateValidator(MockLifecycleSectionRefused)
        native, lookup, captures, base = native_and_reads()
        for patch in native.patches:
            transition = patch.prepared.transition
            participant = transition.participants[0]
            if participant.before.status != "present":
                continue
            state = participant.before.state
            foreign_ref = type(state.last_transition)(**{**dict(state.last_transition), "world_uid": "foreign-world"})
            foreign_state = type(state)(**{**dict(state), "last_transition": foreign_ref})
            before = type(participant.before)(state=foreign_state)
            changed_participant = type(participant)(before=before, after=participant.after)
            changed_transition = type(transition)(intent=transition.intent,
                participants=(changed_participant, *transition.participants[1:]))
            with self.subTest(operation=transition.intent.operation, entity=state.entity):
                with self.assertRaisesRegex(ValueError, "another world"):
                    type(patch.prepared)(**{**dict(patch.prepared), "transition": changed_transition})
                changed_captures = tuple(type(c)(publication=base, last_transitions=c.last_transitions,
                    entities=tuple(before if f.status == "present" and f.state.entity == state.entity else f
                                   for f in c.entities)) for c in captures)
                # Current-reader provenance is checked independently of native
                # before comparison, including accepted equal retries.
                for found in ((), tuple(range(8))):
                    _, accepted, _, _ = native_and_reads(found)
                    with self.assertRaisesRegex(ValueError, "another world"):
                        validator.validate(native, accepted=accepted, captures=changed_captures, expected_world=base)

    def test_native_prepared_rejects_reason_for_another_operation(self):
        native, lookup, captures, base = native_and_reads()
        for index, patch in enumerate(native.patches):
            prepared = patch.prepared
            transition = prepared.transition
            intent = transition.intent
            wrong = (LifecycleOperation.END if intent.operation is not LifecycleOperation.END
                     else LifecycleOperation.CREATE)
            reason = type(intent.reason)(**{**dict(intent.reason), "operation": wrong})
            intent = type(intent)(**{**dict(intent), "reason": reason})
            transition = type(transition)(intent=intent, participants=transition.participants)
            with self.subTest(patch=index):
                with self.assertRaisesRegex(ValueError, "reason.operation"):
                    type(prepared)(**{**dict(prepared), "transition": transition})
                # Unchecked copies must also fail revalidation at apply admission.
                malformed_patch = patch.model_copy(update={
                    "prepared": prepared.model_copy(update={"transition": transition})})
                malformed = native.model_copy(update={"patches": (
                    *native.patches[:index], malformed_patch, *native.patches[index + 1:])})
                with self.assertRaisesRegex(ValueError, "reason.operation"):
                    LifecycleStateValidator(MockLifecycleSectionRefused).validate(
                        malformed, accepted=lookup, captures=captures, expected_world=base)

    def test_new_reactivate_requires_matching_end_history(self):
        native, lookup, captures, base = native_and_reads()
        validator = LifecycleStateValidator(MockLifecycleSectionRefused)
        self.assertIs(type(validator.validate(native, accepted=lookup, captures=captures,
                                             expected_world=base)), SectionAccepted)
        for capture_index, capture in enumerate(captures):
            fact = capture.last_transitions[0]
            variants = {
                "missing": (),
                "duplicate": (fact, fact),
                "replacement": (fact.model_copy(update={"operation": LifecycleOperation.REPLACEMENT}),),
                "create": (fact.model_copy(update={"operation": LifecycleOperation.CREATE}),),
                "reactivate": (fact.model_copy(update={"operation": LifecycleOperation.REACTIVATE}),),
                "wrong_ref": (fact.model_copy(update={"ref": fact.ref.model_copy(update={"change_uid": "other"})}),),
                "wrong_entity": (fact.model_copy(update={"entity": fact.entity.model_copy(update={"entity_uid": "other"})}),),
            }
            for name, facts in variants.items():
                with self.subTest(kind=capture_index, case=name):
                    changed = list(captures)
                    changed[capture_index] = type(capture)(publication=base, entities=capture.entities,
                                                          last_transitions=facts)
                    with self.assertRaisesRegex(ValueError, "Reactivate"):
                        validator.validate(native, accepted=lookup, captures=tuple(changed), expected_world=base)

    def test_equal_reactivate_retry_does_not_require_old_history(self):
        native, lookup, captures, base = native_and_reads((6, 7))
        validator = LifecycleStateValidator(MockLifecycleSectionRefused)
        for replacement_history in (False, True):
            changed = tuple(type(c)(publication=base, entities=c.entities, last_transitions=tuple(
                f.model_copy(update={"operation": LifecycleOperation.REPLACEMENT}) for f in c.last_transitions)
                if replacement_history else ()) for c in captures)
            self.assertIs(type(validator.validate(native, accepted=lookup, captures=changed,
                                                 expected_world=base)), SectionAccepted)

    def test_native_constructor_cannot_bypass_required_transition_coverage(self):
        native, _, _, base = native_and_reads()
        entry = native.domain_evidence[0]
        variants = {
            "empty": (),
            "partial": native.domain_evidence[1:],
            "duplicate": (*native.domain_evidence, entry),
            "extra": (*native.domain_evidence, entry.model_copy(update={"change_uid": "unrelated"})),
            "change": (entry.model_copy(update={"change_uid": "unrelated"}), *native.domain_evidence[1:]),
            "entity": (entry.model_copy(update={"effect": entry.effect.model_copy(update={
                "entity": entry.effect.entity.model_copy(update={"entity_uid": "unrelated"})})}), *native.domain_evidence[1:]),
            "effect": (entry.model_copy(update={"effect": entry.effect.model_copy(update={
                "effect": LifecycleOperation.CREATE if entry.effect.effect is not LifecycleOperation.CREATE else LifecycleOperation.END})}), *native.domain_evidence[1:]),
            "action": (entry.model_copy(update={"effect": entry.effect.model_copy(update={
                "reason_action_uid": "unrelated"})}), *native.domain_evidence[1:]),
        }
        # Direct constructors, no model_construct; the semantic gate must run
        # before any dependency on the caller's claimed source projection.
        for name, evidence in variants.items():
            with self.subTest(name=name):
                malformed = type(native)(header=native.header.model_copy(update={"depends_on": ()}),
                                         patches=native.patches, domain_evidence=evidence)
                with self.assertRaisesRegex(ValueError, "domain_evidence"):
                    MockLifecycleEvidenceValidator().validate(malformed, prepared_domain_sections=(),
                        expected_world=base, operation_id="publish")

    def test_native_evidence_requires_all_matching_refs_in_source_order(self):
        pairs = [sections.prepared_and_coverage(LifecycleOperation.CREATE, "A", i) for i in range(2)]
        source = subject_section()
        effects = tuple(coverage[0].effect for _, coverage in pairs)
        patches = tuple(patch.model_copy(update={
            "effects": effects,
            "mutations": tuple(mutation.model_copy(update={"entity": effect.entity})
                               for mutation, effect in zip(patch.mutations, effects, strict=True))
        }) for patch in source.patches)
        source = source.model_copy(update={"patches": patches})
        refs = tuple(p.header.ref for p in patches)
        evidence = tuple(coverage[0].model_copy(update={"patch_refs": refs}) for _, coverage in pairs)
        request = m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=patches[0].base,
            changes=tuple(prepared for prepared, _ in pairs), domain_evidence=evidence)
        native = LifecycleSectionPipelineOpenPipeline(binding=sections.section_binding()).prepare_section(request)
        validator = MockLifecycleEvidenceValidator()
        def validate(value):
            return validator.validate(value, prepared_domain_sections=(source,), expected_world=request.expected_world, operation_id="publish")
        self.assertIs(type(MockSubjectPayloadVerifierA().verify(source)), SectionAccepted)
        self.assertIs(type(validate(native)), SectionAccepted)
        for wrong_refs in ((refs[0],), tuple(reversed(refs))):
            bad = native.model_copy(update={"domain_evidence": (
                native.domain_evidence[0].model_copy(update={"patch_refs": wrong_refs}), *native.domain_evidence[1:])})
            result = validate(bad)
            self.assertEqual(result.diagnostics[0].path.projection(), ("domain_evidence", 0, "patch_refs"))
        bad = native.model_copy(update={"domain_evidence": (
            native.domain_evidence[0].model_copy(update={"patch_refs": (refs[0].model_copy(update={"ordinal": 99}),)}),
            *native.domain_evidence[1:])})
        self.assertEqual(validate(bad).diagnostics[0].path.projection(), ("domain_evidence", 0, "patch_refs", 0))
        with self.assertRaises(ValueError):
            validator.validate(native, prepared_domain_sections=(), expected_world=request.expected_world, operation_id="publish")

    def test_new_mixed_and_equal_retry_state_rules(self):
        validator = LifecycleStateValidator(MockLifecycleSectionRefused)
        for found in ((), (0, 2), tuple(range(8))):
            native, lookup, captures, base = native_and_reads(found)
            # Accepted transitions may already have their after projection.
            replacements = {p.after.entity: p.after for index, patch in enumerate(native.patches) if index in found
                            for p in patch.prepared.transition.participants}
            captures = tuple(type(c)(publication=base, entities=tuple(
                (m.PresentA if isinstance(replacements.get(f.state.entity if f.status == "present" else f.entity), m.EntityStateA) else m.PresentB)(
                    state=replacements[f.state.entity if f.status == "present" else f.entity])
                if (f.state.entity if f.status == "present" else f.entity) in replacements else f
                for f in c.entities), last_transitions=c.last_transitions) for c in captures)
            self.assertIs(type(validator.validate(native, accepted=lookup, captures=captures, expected_world=base)), SectionAccepted)

    def test_conflicts_aggregate_in_original_patch_order(self):
        native, lookup, captures, base = native_and_reads((0,))
        changed = lookup.entries[0].transition
        changed = changed.model_copy(update={"intent": changed.intent.model_copy(
            update={"reason": changed.intent.reason.model_copy(update={"action_uid": "different"})})})
        lookup = lookup.model_copy(update={"entries": (lookup.entries[0].model_copy(update={"transition": changed}), *lookup.entries[1:])})
        # Second A transition is new Replacement: present predecessor is now absent.
        capture = captures[0]
        index = next(i for i, fact in enumerate(capture.entities) if fact.status == "present")
        facts = list(capture.entities)
        facts[index] = m.AbsentA(entity=facts[index].state.entity)
        captures = (capture.model_copy(update={"entities": tuple(facts)}), captures[1])
        result = LifecycleStateValidator(MockLifecycleSectionRefused).validate(native, accepted=lookup, captures=captures, expected_world=base)
        self.assertIs(type(result), MockLifecycleSectionRefused)
        self.assertEqual([i.code for i in result.diagnostics],
                         [LifecycleApplyCode.CHANGE_PAYLOAD_CONFLICT, LifecycleApplyCode.BEFORE_STATE_MISMATCH])
        self.assertEqual([i.path.projection() for i in result.diagnostics],
            [("patches", 0, "prepared", "transition", "intent", "change_uid"),
             ("patches", 2, "prepared", "transition", "participants", 0, "before")])

    def test_incomplete_lookup_and_capture_are_faults(self):
        native, lookup, captures, base = native_and_reads()
        validator = LifecycleStateValidator(MockLifecycleSectionRefused)
        with self.assertRaises(ValueError):
            validator.validate(native, accepted=lookup.model_copy(update={"entries": lookup.entries[:-1]}), captures=captures, expected_world=base)
        with self.assertRaises(ValueError):
            validator.validate(native, accepted=lookup, captures=captures[:1], expected_world=base)

    def test_subject_many_to_many_and_false_effect(self):
        for suffix, verifier in (("A", MockSubjectPayloadVerifierA()), ("B", MockSubjectPayloadVerifierB())):
            section = subject_section(suffix)
            self.assertIs(type(verifier.verify(section)), SectionAccepted)
            patch = section.patches[0]
            bad = section.model_copy(update={"patches": (patch.model_copy(update={
                "effects": tuple(e.model_copy(update={"effect": LifecycleOperation.END}) for e in patch.effects)}), section.patches[1])})
            result = verifier.verify(bad)
            self.assertIs(type(result), MockSubjectSectionRefused)
            self.assertEqual([i.code for i in result.diagnostics], [d.MockSubjectCode.EFFECT_PAYLOAD_MISMATCH])
            self.assertEqual(result.diagnostics[0].path.projection(), ("patches", 0, "effects"))
            incomplete = section.model_copy(update={"patches": (section.patches[0],)})
            self.assertEqual(verifier.verify(incomplete).diagnostics[0].code, d.MockSubjectCode.INCOMPLETE_EFFECT)

    def test_subject_independent_failures_aggregate(self):
        section = subject_section()
        patch = section.patches[0]
        bad = patch.mutations[0].model_copy(update={"before": True, "after": True})
        section = section.model_copy(update={"patches": (patch.model_copy(update={"mutations": (bad, *patch.mutations[1:])}),)})
        result = MockSubjectPayloadVerifierA().verify(section)
        self.assertEqual([i.code for i in result.diagnostics], [
            d.MockSubjectCode.INVALID_MUTATION, d.MockSubjectCode.EFFECT_PAYLOAD_MISMATCH, d.MockSubjectCode.INCOMPLETE_EFFECT])
