"""Own closed A/B projection of source-owned immutable public claims."""
from typing import cast
from app.application.lifecycle.validation.evidenceValidator import LifecycleEvidenceValidator, SubjectSectionClaims
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.results.sectionResult import SectionAccepted
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from tests.lifecycle.support.mixedContracts import LifecycleSectionAB, CoverageA
from tests.lifecycle.support.domainSections import TestDomainSectionA, TestDomainSectionB
from tests.lifecycle.support.snapshotContracts import MockLifecycleSectionRefused
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext


class MockLifecycleEvidenceValidator:
    def validate(self, section: LifecycleSectionAB, *,
                 prepared_domain_sections: tuple[TestDomainSectionA | TestDomainSectionB, ...],
                 expected_world: WorldPublicationRef, operation_id: EntityUid,
                 ) -> SectionAccepted | MockLifecycleSectionRefused:
        models = {entry.section.section_key: TestDomainSectionA if type(entry) is CoverageA else TestDomainSectionB
                  for entry in section.domain_evidence}
        for source in prepared_domain_sections:
            if type(source) is not models.get(source.header.key):
                raise TypeError("admitted subject projection has the wrong exact A/B model")
        # Read-only structural projection after the closed source-class check.
        # No callback, source codec, copied payload or validation cache.
        projection = cast(tuple[SubjectSectionClaims, ...], prepared_domain_sections)
        return LifecycleEvidenceValidator(MockLifecycleSectionRefused).validate(
            section, prepared_domain_sections=projection, expected_world=expected_world, operation_id=operation_id)


class MockLifecycleEvidenceBinding:
    def validate(self, section: LifecycleSectionAB, context: SnapshotValidationContext) -> SectionAccepted | MockLifecycleSectionRefused:
        sources: list[TestDomainSectionA | TestDomainSectionB] = []
        seen: set[str] = set()
        for entry in section.domain_evidence:
            if entry.section not in context.resolved_dependencies:
                raise ValueError("Lifecycle evidence dependency was not resolved by Snapshot")
            key = entry.section.section_key
            if key in seen:
                continue
            seen.add(key)
            source = (context.admitted_sections.require(key, model=TestDomainSectionA)
                      if type(entry) is CoverageA else
                      context.admitted_sections.require(key, model=TestDomainSectionB))
            sources.append(source)
        return MockLifecycleEvidenceValidator().validate(section, prepared_domain_sections=tuple(sources),
            expected_world=context.expected_world, operation_id=context.operation_id)
