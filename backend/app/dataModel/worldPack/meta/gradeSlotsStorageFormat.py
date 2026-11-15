"""Shared storage descriptor of tile and location grade sidecars."""

from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey

GRADE_SLOTS_FORMAT_KEY: ArtifactFormatKey = RegistryKey[ArtifactFormatRegistry]("world_pack.grade_slots.json")
GRADE_SLOTS_STORAGE_VERSION = 1
