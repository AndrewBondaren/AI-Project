"""Shared descriptor for wilderness and location fine terrain blobs."""

from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactFormatRegistry
from app.dataModel.patch.values import FormatVersion
from app.dataModel.registryKey import RegistryKey

FINE_TERRAIN_FORMAT_KEY: ArtifactFormatKey = RegistryKey[ArtifactFormatRegistry]("world_pack.fine_terrain.zstd")
FINE_TERRAIN_STORAGE_VERSION: FormatVersion = 1
