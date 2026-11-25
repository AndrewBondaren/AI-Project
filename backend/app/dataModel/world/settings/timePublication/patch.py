from typing import Self
from pydantic import ModelWrapValidatorHandler, ValidationInfo, model_validator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.time.changes.admission import raw_field, valid_field, json_collections
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange
from .native import admit

SETTINGS_SECTION = RegistryKey[PatchSectionRegistry]("world_time_settings")
WORLD_TIME_SETTINGS_PATCH_FORMAT = 1


class WorldTimeSettingsPatch(PatchData):
    change: PreparedTimeSettingsChange

    @model_validator(mode="wrap")
    @classmethod
    def native_header(cls, value: object, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo) -> Self:
        if info.mode == "json":
            value = json_collections(value)
        header_field = FieldRef(lambda: WorldTimeSettingsPatch, lambda v: v.header)
        ref_field = FieldRef(lambda: PatchHeader, lambda v: v.ref)
        header = raw_field(value, header_field)
        ref = raw_field(header, ref_field)
        change = raw_field(value, FieldRef(lambda: WorldTimeSettingsPatch, lambda v: v.change))
        operation = valid_field(change, FieldRef(lambda: PreparedTimeSettingsChange, lambda v: v.operation_id))
        path = CheckedPath.root(WorldTimeSettingsPatch).field(header_field)
        ref_path = path.field(ref_field)
        return admit(cls, value, handler, (
            (ref_path, ref, FieldRef(lambda: PatchRef, lambda v: v.section_key), SETTINGS_SECTION),
            (ref_path, ref, FieldRef(lambda: PatchRef, lambda v: v.ordinal), 0),
            (ref_path, ref, FieldRef(lambda: PatchRef, lambda v: v.operation_id), operation),
            (path, header, FieldRef(lambda: PatchHeader, lambda v: v.format_version), WORLD_TIME_SETTINGS_PATCH_FORMAT),
            (path, header, FieldRef(lambda: PatchHeader, lambda v: v.depends_on), ()),
            (path, header, FieldRef(lambda: PatchHeader, lambda v: v.artifacts), ()),
        ))
