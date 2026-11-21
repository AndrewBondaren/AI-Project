"""Read-only access to the exact sections of one admitted attempt."""
from dataclasses import dataclass
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection


@dataclass(frozen=True, slots=True)
class AdmittedSectionView:
    _request: PatchSet
    _read_scope: CommitReadScope
    _sections: tuple[DomainSection, ...]

    def require[S: DomainSection](self, key: SectionKey, *, model: type[S]) -> S:
        self._read_scope.assert_active()
        matches = tuple(section for section in self._sections if section.header.key == key)
        if len(matches) != 1 or type(matches[0]) is not model:
            raise PublicationInfrastructureError("admitted section key/model does not match")
        return matches[0]

    def assert_bound(self, request: PatchSet, scope: CommitReadScope) -> None:
        scope.assert_active()
        if self._request is not request or self._read_scope is not scope or self._sections is not request.sections:
            raise PublicationInfrastructureError("admitted section view belongs to another request or scope")
