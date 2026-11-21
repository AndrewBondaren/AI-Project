"""Bind already admitted immutable input to the current borrowed read scope."""
from pydantic import BaseModel
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.admittedSectionView import AdmittedSectionView
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.dependency import SectionDependency
from app.dataModel.patch.sections.section import DomainSection


def _immutable(value: object) -> bool:
    if isinstance(value, BaseModel):
        return bool(type(value).model_config.get("frozen")) and all(
            _immutable(getattr(value, name)) for name in type(value).model_fields)
    if isinstance(value, (tuple, frozenset)):
        return all(_immutable(item) for item in value)
    return value is None or isinstance(value, (str, bytes, int, float, bool))


class SnapshotAttemptContextBuilder:
    def __init__(self, *, registry: SectionRegistry) -> None:
        self._registry = registry

    def build[S: DomainSection](self, request: PatchSet[S], *, scope: CommitReadScope,
                                resolved_dependencies: tuple[SectionDependency, ...]) -> SnapshotValidationContext:
        scope.assert_active()
        type(request).model_validate(request, strict=True)
        if not _immutable(request):
            raise PublicationInfrastructureError("admitted request must be deeply immutable")
        for section in request.sections:
            self._registry.resolve(section)
        view = AdmittedSectionView(request, scope, request.sections)
        return SnapshotValidationContext(request.operation_id, request.expected_world,
            request.expected_players, resolved_dependencies, scope, view)

    def assert_bound[S: DomainSection](self, context: SnapshotValidationContext, *,
                                       request: PatchSet[S], scope: CommitReadScope) -> None:
        context.admitted_sections.assert_bound(request, scope)
        if (context.read_scope is not scope or context.operation_id != request.operation_id
                or context.expected_world != request.expected_world or context.expected_players != request.expected_players):
            raise PublicationInfrastructureError("validation context differs from admitted attempt")
        for section in request.sections:
            self._registry.resolve(section)
