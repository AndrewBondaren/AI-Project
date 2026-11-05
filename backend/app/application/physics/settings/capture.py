"""Pure content identity. A view here provides no publication pinning guarantee."""

from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView, settings_ref
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.immutableValue import validate_immutable

def build_settings_view(world_uid: EntityUid, settings: WorldPhysicsSettings) -> WorldPhysicsSettingsView:
    return WorldPhysicsSettingsView(settings=settings, ref=settings_ref(world_uid, settings))


def validate_settings_view(view: WorldPhysicsSettingsView) -> WorldPhysicsSettingsView:
    validate_immutable(view)
    return WorldPhysicsSettingsView.model_validate(view, strict=True)
