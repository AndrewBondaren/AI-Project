"""Physics-owned custom validator codes at the Pydantic boundary."""

from enum import StrEnum


class PhysicsSettingsValidationCode(StrEnum):
    WORLD = "physics_settings_world"
    SCHEMA = "physics_settings_schema"
    CONTENT = "physics_settings_content"
    IMMUTABLE = "physics_settings_immutable"
