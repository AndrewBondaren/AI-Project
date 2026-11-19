"""Pure relation checks shared by the result model and admission adapters."""

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.request.patchSetData import PatchSetData
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.validation.invariantDetails import (
    DuplicatePatchOrdinalDetails, DuplicatePlayerDetails, DuplicateSectionDetails,
    MissingPackDetails, MissingPreparedDependencyDetails, PatchOperationMismatchDetails,
    PatchSectionMismatchDetails, PreparedDependencyOrderDetails, WorldMismatchDetails,
)
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.values import PatchOrdinal
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class PatchSetInvariants:
    @staticmethod
    def check_core[S: DomainSection](data: PatchSetData[S]) -> tuple[PatchSetInvariantViolation, ...]:
        errors = ValidatorAggregationHelper((PatchSetInvariantViolation,))
        if data.expected_world.world_uid != data.world_uid:
            errors.add(PatchSetInvariantViolation(details=WorldMismatchDetails(
                expected_world_uid=data.world_uid, actual_world_uid=data.expected_world.world_uid)))
        if data.expected_world.pack_hash is None:
            errors.add(PatchSetInvariantViolation(details=MissingPackDetails(publication=data.expected_world)))
        players: dict[EntityUid, int] = {}
        for index, player in enumerate(data.expected_players):
            if player.player_uid in players:
                errors.add(PatchSetInvariantViolation(details=DuplicatePlayerDetails(player_uid=player.player_uid),
                    player_index=index, related_index=players[player.player_uid]))
            else:
                players[player.player_uid] = index
        sections: dict[SectionKey, int] = {}
        for index, section in enumerate(data.sections):
            if section.header.key in sections:
                errors.add(PatchSetInvariantViolation(details=DuplicateSectionDetails(section_key=section.header.key),
                    section_index=index, related_index=sections[section.header.key]))
            else:
                sections[section.header.key] = index
        for section_index, section in enumerate(data.sections):
            ordinals: dict[PatchOrdinal, int] = {}
            for patch_index, patch in enumerate(section.patches):
                ref = patch.header.ref
                if ref.operation_id != data.operation_id:
                    errors.add(PatchSetInvariantViolation(details=PatchOperationMismatchDetails(
                        patch_ref=ref, expected_operation_id=data.operation_id),
                        section_index=section_index, patch_index=patch_index))
                if ref.section_key != section.header.key:
                    errors.add(PatchSetInvariantViolation(details=PatchSectionMismatchDetails(
                        patch_ref=ref, expected_section_key=section.header.key),
                        section_index=section_index, patch_index=patch_index))
                if ref.ordinal in ordinals:
                    errors.add(PatchSetInvariantViolation(details=DuplicatePatchOrdinalDetails(
                        section_key=section.header.key, ordinal=ref.ordinal), section_index=section_index,
                        patch_index=patch_index, related_index=ordinals[ref.ordinal]))
                else:
                    ordinals[ref.ordinal] = patch_index
        return errors.snapshot()

    @staticmethod
    def check_prepared_order[S: DomainSection](data: PatchSetData[S]) -> tuple[PatchSetInvariantViolation, ...]:
        positions: dict[SectionKey, list[int]] = {}
        for index, section in enumerate(data.sections):
            positions.setdefault(section.header.key, []).append(index)
        errors = ValidatorAggregationHelper((PatchSetInvariantViolation,))
        for index, section in enumerate(data.sections):
            for dependency_index, dependency in enumerate(section.header.depends_on):
                if not isinstance(dependency, PreparedSectionDependency):
                    continue
                targets = positions.get(dependency.section_key, [])
                if not targets:
                    errors.add(PatchSetInvariantViolation(details=MissingPreparedDependencyDetails(
                        source_section_key=section.header.key, missing_section_key=dependency.section_key),
                        section_index=index, dependency_index=dependency_index))
                elif len(targets) == 1 and targets[0] > index:
                    errors.add(PatchSetInvariantViolation(details=PreparedDependencyOrderDetails(
                        source_section_key=section.header.key, dependency_section_key=dependency.section_key),
                        section_index=index, dependency_index=dependency_index, related_index=targets[0]))
        return errors.snapshot()
