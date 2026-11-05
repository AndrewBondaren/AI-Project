"""Pure content identity. A view here provides no publication pinning guarantee."""

from pydantic import TypeAdapter

from app.application.encoding.canonicalCodec import content_digest, encode
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef, WorldPhysicsSettingsView
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.immutableValue import validate_immutable

_PRIMITIVE_MANIFEST = CanonicalSchemaManifest(entries=())


def build_settings_view(world_uid: EntityUid, settings: WorldPhysicsSettings) -> WorldPhysicsSettingsView:
    validate_immutable(settings)
    settings = WorldPhysicsSettings.model_validate(settings, strict=True)
    # Validate identity before hashing; no ad-hoc normalization of world IDs.
    world_uid = TypeAdapter(EntityUid).validate_python(world_uid, strict=True)
    projection = (settings.SCHEMA_ID, settings.SCHEMA_VERSION, world_uid,
                  tuple((name, getattr(settings, name)) for name in WorldPhysicsSettings.model_fields))
    revision = content_digest(encode(projection, _PRIMITIVE_MANIFEST)).hex()
    return WorldPhysicsSettingsView(settings=settings, ref=WorldPhysicsSettingsRef(
        world_uid=world_uid, schema_version=settings.SCHEMA_VERSION, content_revision=revision))


def validate_settings_view(view: WorldPhysicsSettingsView) -> WorldPhysicsSettingsView:
    validate_immutable(view)
    view = WorldPhysicsSettingsView.model_validate(view, strict=True)
    if view.ref != build_settings_view(view.ref.world_uid, view.settings).ref:
        raise ValueError("settings view content or schema version does not match its ref")
    return view
