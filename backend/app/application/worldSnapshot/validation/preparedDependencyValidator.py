"""Compare prepared dependency claims with the owning exact section encoding."""
from app.application.patch.encoding.sectionFingerprint import SectionFingerprint
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode, SnapshotApplyRelationIssue


class SnapshotPreparedDependencyValidator:
    def __init__(self, *, fingerprints: SectionFingerprint) -> None:
        if not isinstance(fingerprints, SectionFingerprint):
            raise TypeError("expected owning SectionFingerprint")
        self._fingerprints = fingerprints

    def validate[S: DomainSection](self, request: PatchSet[S]) -> tuple[SnapshotApplyRelationIssue, ...]:
        sections = {section.header.key: section for section in request.sections}
        if len(sections) != len(request.sections):
            raise PublicationInfrastructureError("duplicate admitted section key")
        digests = {}
        errors = ValidatorAggregationHelper((SnapshotApplyRelationIssue,))
        for section in request.sections:
            mismatch = False
            for dependency in section.header.depends_on:
                if not isinstance(dependency, PreparedSectionDependency):
                    continue
                try:
                    target = sections[dependency.section_key]
                    if dependency.section_key not in digests:
                        digests[dependency.section_key] = self._fingerprints.fingerprint(target)
                except PublicationInfrastructureError:
                    raise
                except Exception as error:
                    raise PublicationInfrastructureError("could not fingerprint admitted dependency") from error
                mismatch |= digests[dependency.section_key] != dependency.section_fingerprint
            if mismatch:
                errors.add(SnapshotApplyRelationIssue(code=SnapshotApplyCode.DEPENDENCY_MISMATCH,
                    section_key=section.header.key, player_uid=None, artifact=None))
        return errors.snapshot()
