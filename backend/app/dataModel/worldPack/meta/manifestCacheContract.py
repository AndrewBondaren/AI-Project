"""RAM namespace for the verified bytes of a World Pack manifest."""
from app.dataModel.cache.contracts.cacheContract import CacheContract, CacheContractRegistry, CacheSchemaVersion
from app.dataModel.registryKey import RegistryKey


MANIFEST_BYTES_CONTRACT = CacheContract[bytes](
    id=RegistryKey[CacheContractRegistry]("world_pack.manifest_bytes"),
    schema_version=CacheSchemaVersion(1),
)
