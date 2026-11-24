import unittest
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.lifecycle.results.issues import LifecycleRelationCode as Code
from tests.lifecycle.support import domainSections as d, evidenceBuilder as builders
from tests.lifecycle.test_apply_predicates import subject_section


class EvidenceBuilderTests(unittest.TestCase):
    def test_many_to_many_and_independent_refusals(self):
        for suffix in ("A", "B"):
            section = subject_section(suffix)
            link_model = getattr(d, "MockEffectLink" + suffix)
            links = tuple(link_model(change_uid=f"change-{i}", effect=e)
                for i, e in enumerate(section.patches[0].effects))
            request = getattr(d, "BuildMockEvidence" + suffix)(section=section,
                dependency=PreparedSectionDependency(section_key=section.header.key, section_fingerprint="a" * 64),
                links=links)
            builder = getattr(builders, "MockLifecycleEvidenceBuilder" + suffix)()
            result = builder.build(request)
            self.assertEqual(len(result), 2)
            for coverage, link in zip(result, links, strict=True):
                self.assertEqual(coverage.effect, link.effect)
                self.assertEqual(coverage.patch_refs, tuple(p.header.ref for p in section.patches))
                self.assertEqual(coverage.section, request.dependency)
            missing = links[0].model_copy(update={"effect": links[0].effect.model_copy(update={"reason_action_uid": "missing"})})
            bad = request.model_copy(update={
                "dependency": request.dependency.model_copy(update={"section_key": "foreign"}),
                "links": (*links, links[0], missing)})
            refused = builder.build(bad)
            self.assertEqual([i.code for i in refused.issues],
                             [Code.PATCH_SECTION_MISMATCH, Code.COVERAGE_DUPLICATE, Code.COVERAGE_MISSING])
            self.assertEqual([i.path.projection() for i in refused.issues],
                             [("dependency", "section_key"), ("links", 2), ("links", 3, "effect")])
