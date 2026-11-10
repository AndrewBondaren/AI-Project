"""Storage identity shared by candidate references and the Pack format binding."""
from app.dataModel.artifacts.references import ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey


MANIFEST_FORMAT_KEY = RegistryKey[ArtifactFormatRegistry]("world_pack.manifest.json")
MANIFEST_STORAGE_VERSION = 1
