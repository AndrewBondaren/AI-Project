"""Storage descriptor of the ordered locations index JSON payload."""

from app.dataModel.artifacts.references import ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey

LOCATIONS_INDEX_FORMAT_KEY = RegistryKey[ArtifactFormatRegistry]("world_pack.locations_index.json")
LOCATIONS_INDEX_FORMAT_VERSION = 1
