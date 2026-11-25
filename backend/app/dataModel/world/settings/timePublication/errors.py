from enum import StrEnum
from typing import Self
from pydantic import Field, model_validator
from app.dataModel.world.calendar.scalars import CalendarRecord
from .section import PrepareTimeSettingsSection


class SettingsSectionIssueCode(StrEnum):
    OPERATION_MISMATCH = "time.settings_section.operation_mismatch"
    PUBLICATION_MISMATCH = "time.settings_section.publication_mismatch"
    SCOPE_MISMATCH = "time.settings_section.scope_mismatch"


class SettingsSectionRelationIssue(CalendarRecord):
    code: SettingsSectionIssueCode
    request: PrepareTimeSettingsSection

    @model_validator(mode="after")
    def actual_mismatch(self) -> Self:
        request = self.request
        expected = request.expected_world
        point = request.change.effective_at
        match self.code:
            case SettingsSectionIssueCode.OPERATION_MISMATCH:
                mismatch = request.change.operation_id != request.operation_id
            case SettingsSectionIssueCode.PUBLICATION_MISMATCH:
                mismatch = request.change.expected != expected
            case SettingsSectionIssueCode.SCOPE_MISMATCH:
                mismatch = (not expected.gameplay_started or point.world_uid != expected.world_uid
                            or point.timeline_id != expected.active_timeline_id)
        if not mismatch:
            raise ValueError("issue must describe an actual context mismatch")
        return self


class SettingsSectionContextMismatch(CalendarRecord):
    issues: tuple[SettingsSectionRelationIssue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def coherent_issues(self) -> Self:
        request = self.issues[0].request
        codes = tuple(issue.code for issue in self.issues)
        expected_order = tuple(code for code in SettingsSectionIssueCode if code in codes)
        if codes != expected_order:
            raise ValueError("issues must be unique and ordered operation/publication/scope")
        if any(issue.request != request for issue in self.issues):
            raise ValueError("all issues must describe the same request")
        return self
