"""Explicit conversion of the documented legacy Earth-relative gravity factor."""

from pydantic import TypeAdapter

from app.dataModel.physics.settings.worldPhysicsSettings import (
    NonnegativeFinite, STANDARD_GRAVITY_M_S2, WorldPhysicsSettings,
)


def normalise_legacy_gravity(earth_factor: float) -> WorldPhysicsSettings:
    factor = TypeAdapter(NonnegativeFinite).validate_python(earth_factor, strict=True)
    return WorldPhysicsSettings(gravity_acceleration_m_s2=factor * STANDARD_GRAVITY_M_S2)
