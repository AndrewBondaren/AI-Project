"""Manifest Cache bindings; importing this module never registers nodes."""

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodes.cache.createCacheEntryNode import CreateCacheEntryNode
from app.application.engine.nodes.cache.evictCacheEntryNode import EvictCacheEntryNode
from app.application.engine.nodes.cache.readCacheEntryNode import ReadCacheEntryNode
from app.application.engine.nodes.cache.updateCacheEntryNode import UpdateCacheEntryNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import (
    CreateManifestCacheEntryInput, CreateManifestCacheEntryOutput,
    ReadManifestCacheEntryInput, ReadManifestCacheEntryOutput,
    UpdateManifestCacheEntryInput, UpdateManifestCacheEntryOutput,
    EvictManifestCacheEntryInput, EvictManifestCacheEntryOutput,
)


READ_MANIFEST_CACHE_ENTRY_CONTRACT = NodeContract(
    input_type=ReadManifestCacheEntryInput,
    output_type=ReadManifestCacheEntryOutput,
    contract_id=ContractId("engine.cache.manifest.read_entry"),
    version=ContractVersion("1"),
    reads=(),
    error_types=(CacheNodeError,),
)


CREATE_MANIFEST_CACHE_ENTRY_CONTRACT = NodeContract(
    input_type=CreateManifestCacheEntryInput,
    output_type=CreateManifestCacheEntryOutput,
    contract_id=ContractId("engine.cache.manifest.create_entry"),
    version=ContractVersion("1"),
    reads=(),
    error_types=(CacheNodeError,),
)


UPDATE_MANIFEST_CACHE_ENTRY_CONTRACT = NodeContract(
    input_type=UpdateManifestCacheEntryInput,
    output_type=UpdateManifestCacheEntryOutput,
    contract_id=ContractId("engine.cache.manifest.update_entry"),
    version=ContractVersion("1"),
    reads=(),
    error_types=(CacheNodeError,),
)


EVICT_MANIFEST_CACHE_ENTRY_CONTRACT = NodeContract(
    input_type=EvictManifestCacheEntryInput,
    output_type=EvictManifestCacheEntryOutput,
    contract_id=ContractId("engine.cache.manifest.evict_entry"),
    version=ContractVersion("1"),
    reads=(),
    error_types=(CacheNodeError,),
)


def register_manifest_cache_nodes(registry: NodeRegistry) -> None:
    registry.register_python(ReadCacheEntryNode, PythonNodeExecutor, READ_MANIFEST_CACHE_ENTRY_CONTRACT)
    registry.register_python(CreateCacheEntryNode, PythonNodeExecutor, CREATE_MANIFEST_CACHE_ENTRY_CONTRACT)
    registry.register_python(UpdateCacheEntryNode, PythonNodeExecutor, UPDATE_MANIFEST_CACHE_ENTRY_CONTRACT)
    registry.register_python(EvictCacheEntryNode, PythonNodeExecutor, EVICT_MANIFEST_CACHE_ENTRY_CONTRACT)
