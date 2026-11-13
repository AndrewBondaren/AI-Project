"""One public Cache eviction of the explicitly supplied key."""

from dataclasses import dataclass, field

from app.application.cache.service.cacheService import CacheFailure, CacheService
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import (
    EvictManifestCacheEntryInput, EvictManifestCacheEntryOutput,
)


@dataclass(frozen=True, kw_only=True)
class EvictCacheEntryNode(PythonNode[EvictManifestCacheEntryInput, EvictManifestCacheEntryOutput, CacheNodeError]):
    id: NodeId = NodeId("evict_cache_entry")
    skip_on_replan: bool = False
    cache: CacheService = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> EvictManifestCacheEntryInput:
        raise RuntimeError("evict_cache_entry requires explicit invocation input")

    async def execute(self, input: EvictManifestCacheEntryInput) -> EvictManifestCacheEntryOutput:
        try:
            result = self.cache.evict(input.request)
        except CacheFailure as exc:
            raise PythonNodeError(CacheNodeError(error=exc.error)) from exc
        return EvictManifestCacheEntryOutput(kind=input.kind, value=result)


def make_evict_cache_entry_node(cache: CacheService) -> EvictCacheEntryNode:
    return EvictCacheEntryNode(cache=cache)
