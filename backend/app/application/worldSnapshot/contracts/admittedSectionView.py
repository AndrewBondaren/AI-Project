"""Read-only access to the exact sections of one admitted attempt."""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection

if TYPE_CHECKING:
    from app.application.worldSnapshot.contracts.context import SnapshotValidationContext


@dataclass(frozen=True, slots=True)
class AdmittedSectionView:
    _request: PatchSet
    _read_scope: CommitReadScope
    _sections: tuple[DomainSection, ...]
    _producer: object | None = field(default=None, repr=False, compare=False)
    _context: SnapshotValidationContext | None = field(default=None, init=False, repr=False, compare=False)

    def _bind_context(self, context: SnapshotValidationContext, *, producer: object) -> None:
        """Finish construction once, before this view is delivered to handlers."""
        if self._producer is not producer or self._context is not None:
            raise PublicationInfrastructureError("attempt view cannot be rebound")
        object.__setattr__(self, "_context", context)

    def _assert_context(self, context: SnapshotValidationContext, *, producer: object) -> None:
        if self._producer is not producer or self._context is not context:
            raise PublicationInfrastructureError("context was not produced for this attempt view")

    def require[S: DomainSection](self, key: SectionKey, *, model: type[S]) -> S:
        self._read_scope.assert_active()
        if self._context is None:
            raise PublicationInfrastructureError("attempt view has not been bound by its producer")
        matches = tuple(section for section in self._sections if section.header.key == key)
        if len(matches) != 1 or type(matches[0]) is not model:
            raise PublicationInfrastructureError("admitted section key/model does not match")
        return matches[0]

    def assert_bound(self, request: PatchSet, scope: CommitReadScope) -> None:
        scope.assert_active()
        if self._request is not request or self._read_scope is not scope or self._sections is not request.sections:
            raise PublicationInfrastructureError("admitted section view belongs to another request or scope")
