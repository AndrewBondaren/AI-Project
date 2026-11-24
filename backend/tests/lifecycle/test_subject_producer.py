import unittest
from app.dataModel.patch.results.sectionResult import SectionAccepted
from tests.lifecycle.support import domainSections as d, subjectMock as subject
from tests.lifecycle.test_apply_predicates import subject_section


class SubjectProducerTests(unittest.TestCase):
    def test_producer_projects_payload_and_groups_admissions(self):
        for suffix in ("A", "B"):
            section = subject_section(suffix)
            request = getattr(d, "PrepareMockSubject" + suffix)(publication=section.patches[0].base,
                operation_id=section.patches[0].header.ref.operation_id,
                batches=tuple(getattr(d, "MockBatch" + suffix)(mutations=p.mutations) for p in section.patches))
            producer = getattr(subject, "MockSubjectProducer" + suffix)()
            prepared = producer.prepare(request)
            self.assertEqual(prepared.section, section)
            self.assertEqual(len(prepared.admissions), 1)
            self.assertEqual(prepared.admissions[0].effects, section.patches[0].effects)
            self.assertIs(type(getattr(subject, "MockSubjectPayloadVerifier" + suffix)().verify(prepared.section)), SectionAccepted)
            mutation = request.batches[0].mutations[0]
            invalid = mutation.model_copy(update={"before": True, "after": True})
            batch = request.batches[0].model_copy(update={"mutations": (invalid, *request.batches[0].mutations[1:])})
            refused = producer.prepare(request.model_copy(update={"batches": (batch,)}))
            self.assertEqual([i.path.projection() for i in refused.diagnostics],
                             [("batches", 0, "mutations", 0, "after"), ("batches",)])
            self.assertEqual([i.code for i in refused.diagnostics],
                             [d.MockSubjectCode.INVALID_MUTATION, d.MockSubjectCode.INCOMPLETE_EFFECT])
