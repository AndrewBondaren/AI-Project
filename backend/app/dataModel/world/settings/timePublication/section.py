from typing import Self
from pydantic import Field, ModelWrapValidatorHandler, ValidationInfo, model_validator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.time.changes.admission import raw_field, json_collections
from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from .patch import WorldTimeSettingsPatch, SETTINGS_SECTION
from .native import admit

WORLD_TIME_SETTINGS_SECTION_FORMAT = 1


class PrepareTimeSettingsSection(CalendarRecord):
    change: PreparedTimeSettingsChange
    operation_id: EntityUid
    expected_world: WorldPublicationRef


class WorldTimeSettingsSection(DomainSection[WorldTimeSettingsPatch]):
    patches: tuple[WorldTimeSettingsPatch, ...] = Field(min_length=1, max_length=1)

    @model_validator(mode="wrap")
    @classmethod
    def native_header(cls, value: object, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo) -> Self:
        if info.mode == "json":
            value = json_collections(value)
        field = FieldRef(lambda: WorldTimeSettingsSection, lambda v: v.header)
        header = raw_field(value, field)
        path = CheckedPath.root(WorldTimeSettingsSection).field(field)
        return admit(cls, value, handler, (
            (path, header, FieldRef(lambda: SectionHeader, lambda v: v.key), SETTINGS_SECTION),
            (path, header, FieldRef(lambda: SectionHeader, lambda v: v.format_version), WORLD_TIME_SETTINGS_SECTION_FORMAT),
            (path, header, FieldRef(lambda: SectionHeader, lambda v: v.depends_on), ()),
        ))
