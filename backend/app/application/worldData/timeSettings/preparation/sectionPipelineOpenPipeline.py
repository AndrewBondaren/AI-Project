from typing import Protocol
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.world.settings.timePublication.patch import WorldTimeSettingsPatch, SETTINGS_SECTION, WORLD_TIME_SETTINGS_PATCH_FORMAT
from app.dataModel.world.settings.timePublication.section import PrepareTimeSettingsSection, WorldTimeSettingsSection, WORLD_TIME_SETTINGS_SECTION_FORMAT
from app.dataModel.world.settings.timePublication.errors import SettingsSectionContextMismatch, SettingsSectionRelationIssue, SettingsSectionIssueCode


class ITimeSettingsSectionPipelineOpenPipeline(Protocol):
    def prepare_section(self, request: PrepareTimeSettingsSection) -> WorldTimeSettingsSection | SettingsSectionContextMismatch: ...


class TimeSettingsSectionPipelineOpenPipeline:
    def prepare_section(self, request: PrepareTimeSettingsSection) -> WorldTimeSettingsSection | SettingsSectionContextMismatch:
        request = PrepareTimeSettingsSection.model_validate(request, strict=True)
        change, expected = request.change, request.expected_world
        errors = ValidatorAggregationHelper((SettingsSectionRelationIssue,))
        checks = (
            (change.operation_id != request.operation_id, SettingsSectionIssueCode.OPERATION_MISMATCH),
            (change.expected != expected, SettingsSectionIssueCode.PUBLICATION_MISMATCH),
            (not expected.gameplay_started or change.effective_at.world_uid != expected.world_uid
             or change.effective_at.timeline_id != expected.active_timeline_id, SettingsSectionIssueCode.SCOPE_MISMATCH),
        )
        for mismatch, code in checks:
            if mismatch:
                errors.add(SettingsSectionRelationIssue(code=code, request=request))
        if issues := errors.snapshot():
            return SettingsSectionContextMismatch(issues=issues)
        patch = WorldTimeSettingsPatch(change=change, header=PatchHeader(
            ref=PatchRef(operation_id=request.operation_id, section_key=SETTINGS_SECTION, ordinal=0),
            format_version=WORLD_TIME_SETTINGS_PATCH_FORMAT, depends_on=(), artifacts=()))
        return WorldTimeSettingsSection(header=SectionHeader(key=SETTINGS_SECTION,
            format_version=WORLD_TIME_SETTINGS_SECTION_FORMAT, depends_on=()), patches=(patch,))
