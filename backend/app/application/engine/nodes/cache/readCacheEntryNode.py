"""One public Cache lookup; miss handling belongs to the calling DAG."""

from dataclasses import dataclass, field

from app.application.cache.service.cacheService import CacheFailure, CacheService
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.cache.contracts import CacheNodeError
from app.dataModel.engine.nodes.cache.manifestContracts import (
    ReadManifestCacheEntryInput, ReadManifestCacheEntryOutput,
)


@dataclass(frozen=True, kw_only=True)
class ReadCacheEntryNode(PythonNode[ReadManifestCacheEntryInput, ReadManifestCacheEntryOutput, CacheNodeError]):
    id: NodeId = NodeId("read_cache_entry")
    skip_on_replan: bool = False
    cache: CacheService = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> ReadManifestCacheEntryInput:
        raise RuntimeError("read_cache_entry requires explicit invocation input")

    async def execute(self, input: ReadManifestCacheEntryInput) -> ReadManifestCacheEntryOutput:
        try:
            lookup = self.cache.get(input.key)
        except CacheFailure as exc:
            raise PythonNodeError(CacheNodeError(error=exc.error)) from exc
        return ReadManifestCacheEntryOutput(key=input.key, lookup=lookup)


def make_read_cache_entry_node(cache: CacheService) -> ReadCacheEntryNode:
    return ReadCacheEntryNode(cache=cache)
