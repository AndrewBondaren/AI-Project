"""Present invariant facts as checked paths; no relation predicates live here."""

from types import UnionType
from typing import Union, get_args, get_origin

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.results.assemblyIssues import PatchSetAssemblyRelationIssue
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.validation.invariantDetails import PatchSetInvariantCode as Code
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef


class PatchSetAssemblyValidator:
    def validate[S: DomainSection](self, request: PatchSetAssemblyInput[S]) -> tuple[PatchSetAssemblyRelationIssue, ...]:
        errors = ValidatorAggregationHelper((PatchSetAssemblyRelationIssue,))
        for fact in (*PatchSetInvariants.check_core(request), *PatchSetInvariants.check_prepared_order(request)):
            path, related = self._paths(request, fact)
            errors.add(PatchSetAssemblyRelationIssue(
                details=fact.details, path=path, related_path=related,
                message=fact.details.code.value.removeprefix("patch_set.assembly.").replace("_", " "),
            ))
        return errors.snapshot()

    @staticmethod
    def _section[S: DomainSection](request: PatchSetAssemblyInput[S], index: int) -> CheckedPath[PatchSetAssemblyInput[S], S]:
        model = type(request)
        path = CheckedPath.root(model).field(FieldRef(lambda: model, lambda value: value.sections)).item(index)
        annotation = unwrap_wire_type(get_args(model.model_fields["sections"].annotation)[0])
        if get_origin(annotation) in (Union, UnionType):
            return path.variant(type(request.sections[index]))
        return path

    @classmethod
    def _key[S: DomainSection](cls, request: PatchSetAssemblyInput[S], index: int) -> ValidatedFieldPath:
        model = type(request.sections[index])
        return cls._section(request, index).field(FieldRef(lambda: model, lambda value: value.header)).field(
            FieldRef(lambda: SectionHeader, lambda value: value.key)).freeze()

    @classmethod
    def _ref[S: DomainSection](cls, request: PatchSetAssemblyInput[S], section_index: int,
                               patch_index: int) -> CheckedPath[PatchSetAssemblyInput[S], PatchRef]:
        section = request.sections[section_index]
        model = type(section)
        path = cls._section(request, section_index).field(
            FieldRef(lambda: model, lambda value: value.patches)).item(patch_index)
        patch_model = type(section.patches[patch_index])
        annotation = unwrap_wire_type(get_args(model.model_fields["patches"].annotation)[0])
        if get_origin(annotation) in (Union, UnionType):
            path = path.variant(patch_model)
        return path.field(FieldRef(lambda: patch_model, lambda value: value.header)).field(
            FieldRef(lambda: PatchHeader, lambda value: value.ref))

    @classmethod
    def _paths[S: DomainSection](cls, request: PatchSetAssemblyInput[S], fact: PatchSetInvariantViolation
                                ) -> tuple[ValidatedFieldPath, ValidatedFieldPath | None]:
        model = type(request)
        root = CheckedPath.root(model)
        code = fact.details.code
        if code is Code.WORLD_MISMATCH:
            return (root.field(FieldRef(lambda: model, lambda value: value.expected_world)).field(
                FieldRef(lambda: WorldPublicationRef, lambda value: value.world_uid)).freeze(),
                root.field(FieldRef(lambda: model, lambda value: value.world_uid)).freeze())
        if code is Code.MISSING_PACK:
            return (root.field(FieldRef(lambda: model, lambda value: value.expected_world)).field(
                FieldRef(lambda: WorldPublicationRef, lambda value: value.pack_hash)).freeze(), None)
        if code is Code.DUPLICATE_PLAYER:
            assert fact.player_index is not None and fact.related_index is not None
            players = root.field(FieldRef(lambda: model, lambda value: value.expected_players))
            selector = FieldRef(lambda: PlayerHeadExpectation, lambda value: value.player_uid)
            return (players.item(fact.player_index).field(selector).freeze(),
                    players.item(fact.related_index).field(selector).freeze())
        assert fact.section_index is not None
        index = fact.section_index
        if code is Code.DUPLICATE_SECTION:
            assert fact.related_index is not None
            return cls._key(request, index), cls._key(request, fact.related_index)
        if code in (Code.MISSING_PREPARED_DEPENDENCY, Code.PREPARED_DEPENDENCY_ORDER):
            assert fact.dependency_index is not None
            section_model = type(request.sections[index])
            path = cls._section(request, index).field(
                FieldRef(lambda: section_model, lambda value: value.header)).field(
                FieldRef(lambda: SectionHeader, lambda value: value.depends_on)).item(
                fact.dependency_index).variant(PreparedSectionDependency).field(
                FieldRef(lambda: PreparedSectionDependency, lambda value: value.section_key)).freeze()
            return path, None if fact.related_index is None else cls._key(request, fact.related_index)
        assert fact.patch_index is not None
        ref = cls._ref(request, index, fact.patch_index)
        if code is Code.PATCH_OPERATION_MISMATCH:
            return (ref.field(FieldRef(lambda: PatchRef, lambda value: value.operation_id)).freeze(),
                    root.field(FieldRef(lambda: model, lambda value: value.operation_id)).freeze())
        if code is Code.PATCH_SECTION_MISMATCH:
            return (ref.field(FieldRef(lambda: PatchRef, lambda value: value.section_key)).freeze(),
                    cls._key(request, index))
        assert code is Code.DUPLICATE_PATCH_ORDINAL and fact.related_index is not None
        selector = FieldRef(lambda: PatchRef, lambda value: value.ordinal)
        return (ref.field(selector).freeze(),
                cls._ref(request, index, fact.related_index).field(selector).freeze())
